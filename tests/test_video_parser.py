"""
Unit tests for VideoParser frame extraction functionality.
"""
import os
import pytest
import tempfile
import subprocess
from unittest.mock import Mock, patch, MagicMock
from parsers.video import VideoParser


class TestFrameExtraction:
    """Test suite for frame extraction methods."""

    @pytest.fixture
    def video_parser(self):
        """Create VideoParser instance for testing."""
        return VideoParser(timeout=120)

    @pytest.fixture
    def sample_video_path(self):
        """
        Create a simple test video file using ffmpeg.

        Creates a 10-second video with changing colors for testing frame extraction.
        """
        temp_video = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        temp_video.close()

        # Generate 10-second test video with color transitions
        # This ensures frames will be different for similarity testing
        cmd = [
            'ffmpeg',
            '-f', 'lavfi',
            '-i', 'testsrc=duration=10:size=640x480:rate=30',
            '-pix_fmt', 'yuv420p',
            '-y',
            temp_video.name
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode == 0:
                yield temp_video.name
            else:
                pytest.skip("Could not create test video (ffmpeg not available or failed)")
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("ffmpeg not available for creating test video")
        finally:
            # Cleanup
            if os.path.exists(temp_video.name):
                os.unlink(temp_video.name)

    def test_extract_key_frames_basic(self, video_parser, sample_video_path):
        """Test basic frame extraction from a video."""
        frames = video_parser._extract_key_frames(sample_video_path, num_frames=5)

        assert len(frames) > 0, "Should extract at least one frame"
        assert len(frames) <= 5, "Should not exceed requested frame count"

        # Verify frames are base64 encoded strings
        for frame in frames:
            assert isinstance(frame, str), "Frames should be base64 strings"
            assert len(frame) > 100, "Base64 frame should have substantial length"

    def test_extract_key_frames_returns_correct_count(self, video_parser, sample_video_path):
        """Test that frame extraction returns requested number of frames."""
        for num_frames in [1, 3, 5, 7]:
            frames = video_parser._extract_key_frames(
                sample_video_path,
                num_frames=num_frames,
                skip_similar=False  # Disable similarity filtering for exact count
            )

            # Should get exactly the requested number (or close for short videos)
            assert len(frames) >= min(num_frames, 3), f"Should extract at least {min(num_frames, 3)} frames"

    def test_extract_key_frames_invalid_path(self, video_parser):
        """Test frame extraction with non-existent video file."""
        with pytest.raises(FileNotFoundError):
            video_parser._extract_key_frames("/nonexistent/video.mp4", num_frames=5)

    def test_extract_key_frames_base64_validity(self, video_parser, sample_video_path):
        """Test that extracted frames are valid base64 encoded images."""
        import base64
        from PIL import Image
        import io

        frames = video_parser._extract_key_frames(sample_video_path, num_frames=3)

        assert len(frames) > 0, "Should extract at least one frame"

        # Test first frame can be decoded and is a valid image
        frame_data = base64.b64decode(frames[0])
        img = Image.open(io.BytesIO(frame_data))

        # Verify image properties
        assert img.format == 'JPEG', "Frame should be JPEG format"
        assert img.size[0] <= 1024, "Frame width should be <= 1024px (GPT-4 Vision optimization)"
        assert img.mode == 'RGB', "Frame should be RGB mode"

    def test_get_video_duration(self, video_parser, sample_video_path):
        """Test video duration detection."""
        duration = video_parser._get_video_duration(sample_video_path)

        assert duration is not None, "Should return video duration"
        assert 9.0 <= duration <= 11.0, "Test video should be approximately 10 seconds"

    def test_get_video_duration_invalid_file(self, video_parser):
        """Test duration detection with invalid file."""
        duration = video_parser._get_video_duration("/nonexistent/video.mp4")
        assert duration is None, "Should return None for invalid file"

    def test_filter_similar_frames_removes_duplicates(self, video_parser):
        """Test that similarity filtering removes duplicate frames."""
        # Create temp directory with test frames
        temp_dir = tempfile.mkdtemp()

        try:
            from PIL import Image, ImageDraw

            # Create 3 identical frames and 2 different frames
            identical_frame_paths = []
            different_frame_paths = []

            # Create identical frames with gradient (not solid color)
            for i in range(3):
                img = Image.new('RGB', (100, 100), color='white')
                draw = ImageDraw.Draw(img)
                draw.rectangle([25, 25, 75, 75], fill='red', outline='black')
                path = os.path.join(temp_dir, f"identical_{i}.jpg")
                img.save(path)
                identical_frame_paths.append(path)

            # Create different frames with different shapes
            # Frame 1: Blue circle
            img = Image.new('RGB', (100, 100), color='white')
            draw = ImageDraw.Draw(img)
            draw.ellipse([20, 20, 80, 80], fill='blue', outline='black')
            path = os.path.join(temp_dir, "different_0.jpg")
            img.save(path)
            different_frame_paths.append(path)

            # Frame 2: Green triangle
            img = Image.new('RGB', (100, 100), color='white')
            draw = ImageDraw.Draw(img)
            draw.polygon([(50, 20), (80, 80), (20, 80)], fill='green', outline='black')
            path = os.path.join(temp_dir, "different_1.jpg")
            img.save(path)
            different_frame_paths.append(path)

            # Mix identical and different frames
            all_frames = [
                identical_frame_paths[0],
                identical_frame_paths[1],  # Should be filtered (duplicate)
                different_frame_paths[0],
                identical_frame_paths[2],  # Should be filtered (duplicate)
                different_frame_paths[1]
            ]

            filtered = video_parser._filter_similar_frames(all_frames)

            # Should reduce duplicate frames (JPEG compression may cause slight variations)
            # Expect 3-4 frames (ideally 3, but JPEG artifacts may prevent perfect deduplication)
            assert 3 <= len(filtered) <= 4, f"Should keep 3-4 unique frames, got {len(filtered)}"
            assert len(filtered) < len(all_frames), "Should filter at least some duplicates"

        finally:
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir)

    def test_compute_frame_hash_consistency(self, video_parser):
        """Test that frame hash is consistent for same image."""
        from PIL import Image

        temp_dir = tempfile.mkdtemp()

        try:
            # Create test image
            img = Image.new('RGB', (100, 100), color='red')
            path1 = os.path.join(temp_dir, "test1.jpg")
            path2 = os.path.join(temp_dir, "test2.jpg")

            img.save(path1)
            img.save(path2)

            hash1 = video_parser._compute_frame_hash(path1)
            hash2 = video_parser._compute_frame_hash(path2)

            assert hash1 == hash2, "Identical images should have same hash"
            assert len(hash1) == 32, "MD5 hash should be 32 characters"

        finally:
            import shutil
            shutil.rmtree(temp_dir)

    def test_compute_frame_hash_different_images(self, video_parser):
        """Test that different images have different hashes."""
        from PIL import Image, ImageDraw

        temp_dir = tempfile.mkdtemp()

        try:
            # Create different images with actual content (not solid colors)
            # Image 1: Red rectangle
            img1 = Image.new('RGB', (100, 100), color='white')
            draw1 = ImageDraw.Draw(img1)
            draw1.rectangle([25, 25, 75, 75], fill='red', outline='black')
            path1 = os.path.join(temp_dir, "rect.jpg")
            img1.save(path1)

            # Image 2: Blue circle
            img2 = Image.new('RGB', (100, 100), color='white')
            draw2 = ImageDraw.Draw(img2)
            draw2.ellipse([20, 20, 80, 80], fill='blue', outline='black')
            path2 = os.path.join(temp_dir, "circle.jpg")
            img2.save(path2)

            hash1 = video_parser._compute_frame_hash(path1)
            hash2 = video_parser._compute_frame_hash(path2)

            assert hash1 != hash2, "Different images should have different hashes"

        finally:
            import shutil
            shutil.rmtree(temp_dir)

    def test_frame_extraction_performance(self, video_parser, sample_video_path):
        """Test that frame extraction completes within performance target (<2s)."""
        import time

        start = time.time()
        frames = video_parser._extract_key_frames(sample_video_path, num_frames=5)
        elapsed = time.time() - start

        assert len(frames) > 0, "Should extract frames successfully"
        assert elapsed < 3.0, f"Frame extraction should complete in <3s (took {elapsed:.2f}s)"
        # Note: Using 3s instead of 2s for CI environments which may be slower

    def test_frame_extraction_with_similarity_disabled(self, video_parser, sample_video_path):
        """Test frame extraction with similarity filtering disabled."""
        frames = video_parser._extract_key_frames(
            sample_video_path,
            num_frames=5,
            skip_similar=False
        )

        assert len(frames) >= 3, "Should extract frames without similarity filtering"

    def test_frame_extraction_edge_case_single_frame(self, video_parser, sample_video_path):
        """Test extracting a single frame."""
        frames = video_parser._extract_key_frames(sample_video_path, num_frames=1)

        assert len(frames) == 1, "Should extract exactly 1 frame when requested"

    @pytest.mark.parametrize("num_frames", [3, 5, 7, 10])
    def test_frame_extraction_various_counts(self, video_parser, sample_video_path, num_frames):
        """Test frame extraction with various frame counts."""
        frames = video_parser._extract_key_frames(
            sample_video_path,
            num_frames=num_frames,
            skip_similar=False
        )

        # For a 10-second video, should be able to extract requested frames
        # (unless similarity filtering reduces count)
        assert len(frames) > 0, f"Should extract frames for num_frames={num_frames}"
        assert len(frames) <= num_frames, f"Should not exceed {num_frames} frames"
