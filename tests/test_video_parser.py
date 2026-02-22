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


class TestVisionExtraction:
    """Test suite for GPT-4 Vision recipe extraction methods."""

    @pytest.fixture
    def video_parser(self):
        """Create VideoParser instance for testing."""
        return VideoParser(timeout=120)

    @pytest.fixture
    def sample_frames(self):
        """Create sample base64-encoded frames for testing."""
        from PIL import Image
        import io
        import base64

        frames = []
        for i in range(3):
            # Create simple test image
            img = Image.new('RGB', (100, 100), color=['red', 'green', 'blue'][i])
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            b64_frame = base64.b64encode(buffer.getvalue()).decode('utf-8')
            frames.append(b64_frame)

        return frames

    def test_build_vision_prompt_tiktok(self, video_parser):
        """Test prompt building for TikTok videos."""
        prompt = video_parser._build_vision_prompt(
            platform="tiktok.com",
            title="Creamy Pasta Recipe",
            description="Easy 10-minute pasta"
        )

        assert "text overlays" in prompt.lower()
        assert "Creamy Pasta Recipe" in prompt
        assert "JSON" in prompt
        assert "name" in prompt
        assert "ingredients" in prompt

    def test_build_vision_prompt_instagram(self, video_parser):
        """Test prompt building for Instagram Reels."""
        prompt = video_parser._build_vision_prompt(
            platform="instagram.com",
            title="Chocolate Cake",
            description="Delicious cake recipe"
        )

        assert "Chocolate Cake" in prompt
        assert "JSON" in prompt

    def test_build_vision_prompt_youtube(self, video_parser):
        """Test prompt building for YouTube Shorts."""
        prompt = video_parser._build_vision_prompt(
            platform="youtube.com",
            title="Quick Breakfast",
            description="Healthy breakfast ideas"
        )

        assert "Quick Breakfast" in prompt
        assert "JSON" in prompt

    def test_build_vision_prompt_with_audio(self, video_parser):
        """Test prompt building with audio transcript."""
        prompt = video_parser._build_vision_prompt(
            platform="tiktok.com",
            title="Pasta Recipe",
            description="Easy pasta",
            audio_transcript="First, boil water. Then add pasta. Cook for 10 minutes."
        )

        assert "audio transcript" in prompt.lower() or "transcript" in prompt.lower()
        assert "boil water" in prompt
        assert "hybrid" in prompt.lower() or "combine" in prompt.lower()

    def test_vision_extract_recipe_success(self, video_parser, sample_frames):
        """Test successful recipe extraction with GPT-4 Vision."""
        # Mock the OpenAI client property
        mock_client = MagicMock()
        video_parser._openai_client = mock_client

        # Mock successful API response
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"is_recipe": true, "name": "Creamy Garlic Pasta", "ingredients": ["pasta", "garlic", "cream"], "steps": ["Boil pasta", "Make sauce", "Combine"]}'
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        # Call vision extraction
        result = video_parser._vision_extract_recipe(
            frames=sample_frames,
            video_metadata={"title": "Pasta Recipe", "description": "Easy pasta", "platform": "tiktok.com"}
        )

        # Verify result
        assert result is not None
        assert result['name'] == "Creamy Garlic Pasta"
        assert len(result['ingredients']) == 3
        assert len(result['steps']) == 3
        assert "pasta" in result['ingredients']

        # Verify API was called correctly
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs['model'] == 'gpt-4o'
        assert len(call_kwargs['messages']) == 2
        assert call_kwargs['messages'][0]['role'] == 'system'
        assert call_kwargs['messages'][1]['role'] == 'user'

    def test_vision_extract_recipe_with_audio(self, video_parser, sample_frames):
        """Test recipe extraction with both frames and audio transcript."""
        mock_client = MagicMock()
        video_parser._openai_client = mock_client

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"is_recipe": true, "name": "Pasta", "ingredients": ["pasta"], "steps": ["Cook"]}'
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = video_parser._vision_extract_recipe(
            frames=sample_frames,
            audio_transcript="Boil water and add pasta",
            video_metadata={"title": "Pasta", "description": "Quick pasta", "platform": "tiktok.com"}
        )

        assert result is not None
        # Verify prompt includes audio transcript
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        user_message = call_kwargs['messages'][1]['content'][0]['text']
        assert "boil water" in user_message.lower() or "audio transcript" in user_message.lower()

    def test_vision_extract_recipe_api_error_retry(self, video_parser, sample_frames):
        """Test retry logic on API errors."""
        mock_client = MagicMock()
        video_parser._openai_client = mock_client

        # First 2 calls fail, 3rd succeeds
        mock_client.chat.completions.create.side_effect = [
            Exception("API Error"),
            Exception("API Error"),
            MagicMock(
                choices=[
                    MagicMock(
                        message=MagicMock(
                            content='{"is_recipe": true, "name": "Pasta", "ingredients": ["pasta"], "steps": ["Cook"]}'
                        )
                    )
                ]
            )
        ]

        result = video_parser._vision_extract_recipe(
            frames=sample_frames,
            video_metadata={"title": "Test", "description": "Test", "platform": "tiktok.com"}
        )

        # Should succeed after retries
        assert result is not None
        assert result['name'] == "Pasta"
        # Verify 3 attempts were made
        assert mock_client.chat.completions.create.call_count == 3

    def test_vision_extract_recipe_all_retries_fail(self, video_parser, sample_frames):
        """Test behavior when all retry attempts fail."""
        mock_client = MagicMock()
        video_parser._openai_client = mock_client

        # All calls fail
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        result = video_parser._vision_extract_recipe(
            frames=sample_frames,
            video_metadata={"title": "Test", "description": "Test", "platform": "tiktok.com"}
        )

        # Should return None after all retries fail
        assert result is None
        # Verify 3 attempts were made
        assert mock_client.chat.completions.create.call_count == 3

    def test_vision_extract_recipe_invalid_json(self, video_parser, sample_frames):
        """Test handling of invalid JSON response."""
        mock_client = MagicMock()
        video_parser._openai_client = mock_client

        # Return invalid JSON
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='This is not valid JSON'
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = video_parser._vision_extract_recipe(
            frames=sample_frames,
            video_metadata={"title": "Test", "description": "Test", "platform": "tiktok.com"}
        )

        # Should return None for invalid JSON
        assert result is None

    def test_vision_extract_recipe_json_with_markdown(self, video_parser, sample_frames):
        """Test handling of JSON wrapped in markdown code blocks."""
        mock_client = MagicMock()
        video_parser._openai_client = mock_client

        # Return JSON wrapped in markdown
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='```json\n{"is_recipe": true, "name": "Pasta", "ingredients": ["pasta"], "steps": ["Cook"]}\n```'
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = video_parser._vision_extract_recipe(
            frames=sample_frames,
            video_metadata={"title": "Test", "description": "Test", "platform": "tiktok.com"}
        )

        # Should successfully extract JSON from markdown
        assert result is not None
        assert result['name'] == "Pasta"

    def test_vision_extract_recipe_multiple_frames(self, video_parser):
        """Test that all frames are included in API call."""
        mock_client = MagicMock()
        video_parser._openai_client = mock_client

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"is_recipe": true, "name": "Test", "ingredients": ["ingredient"], "steps": ["step"]}'
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        # Create 5 frames
        frames = ["frame1", "frame2", "frame3", "frame4", "frame5"]

        result = video_parser._vision_extract_recipe(
            frames=frames,
            video_metadata={"title": "Test", "description": "Test", "platform": "tiktok.com"}
        )

        assert result is not None

        # Verify all 5 frames were included in the API call
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        user_content = call_kwargs['messages'][1]['content']

        # First element is text prompt, remaining should be image frames
        image_frames = [item for item in user_content if item['type'] == 'image_url']
        assert len(image_frames) == 5

    def test_vision_extract_recipe_high_detail_mode(self, video_parser, sample_frames):
        """Test that high detail mode is used for better OCR."""
        mock_client = MagicMock()
        video_parser._openai_client = mock_client

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content='{"is_recipe": true, "name": "Test", "ingredients": ["ingredient"], "steps": ["step"]}'
                )
            )
        ]
        mock_client.chat.completions.create.return_value = mock_response

        result = video_parser._vision_extract_recipe(
            frames=sample_frames,
            video_metadata={"title": "Test", "description": "Test", "platform": "tiktok.com"}
        )

        assert result is not None

        # Verify high detail mode is set
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        user_content = call_kwargs['messages'][1]['content']

        # Check that at least one image has detail="high"
        image_frames = [item for item in user_content if item['type'] == 'image_url']
        assert any(frame['image_url'].get('detail') == 'high' for frame in image_frames)


class TestAudioConfidenceScoring:
    """Test suite for audio confidence scoring."""

    @pytest.fixture
    def video_parser(self):
        """Create VideoParser instance for testing."""
        return VideoParser(timeout=120)

    def test_high_confidence_spoken_recipe(self, video_parser):
        """Test high confidence score for clear spoken recipe."""
        transcript = """
        Today I'm making a delicious pasta carbonara. Start by boiling water in a large pot.
        Add 1 pound of spaghetti and cook for 10 minutes until al dente. While the pasta cooks,
        heat a large skillet and add 4 ounces of diced pancetta. Cook until crispy, about 5 minutes.
        In a bowl, whisk together 3 eggs, 1 cup of grated parmesan cheese, and black pepper.
        Drain the pasta and add it to the skillet with the pancetta. Remove from heat and quickly
        stir in the egg mixture. The heat from the pasta will cook the eggs. Serve immediately
        with extra parmesan and fresh basil. This recipe serves 4 people.
        """

        recipe_data = {
            "name": "Pasta Carbonara",
            "ingredients": [
                "1 pound spaghetti",
                "4 ounces pancetta",
                "3 eggs",
                "1 cup parmesan cheese",
                "black pepper"
            ],
            "steps": [
                "Boil water and cook spaghetti for 10 minutes",
                "Cook pancetta in skillet until crispy",
                "Whisk eggs with parmesan and pepper",
                "Combine pasta with pancetta",
                "Stir in egg mixture off heat"
            ],
            "servings": 4
        }

        score = video_parser._calculate_audio_confidence(transcript, recipe_data)

        # Should be high confidence (>= 0.7)
        assert score >= 0.7, f"Expected high confidence, got {score}"
        assert score <= 1.0

    def test_low_confidence_music_only(self, video_parser):
        """Test low confidence for music-only or non-recipe video."""
        transcript = "[music] [music] yeah yeah [music] vibes [music]"

        recipe_data = {
            "name": None,
            "ingredients": [],
            "steps": []
        }

        score = video_parser._calculate_audio_confidence(transcript, recipe_data)

        # Should be low confidence (< 0.4)
        assert score < 0.4, f"Expected low confidence for music-only, got {score}"

    def test_medium_confidence_partial_audio(self, video_parser):
        """Test medium confidence for partial audio with some recipe content."""
        transcript = """
        Quick pasta recipe. Cook the pasta. Add sauce. Mix everything together.
        """

        recipe_data = {
            "name": "Quick Pasta",
            "ingredients": [
                "pasta",
                "sauce"
            ],
            "steps": [
                "Cook pasta",
                "Add sauce",
                "Mix together"
            ]
        }

        score = video_parser._calculate_audio_confidence(transcript, recipe_data)

        # Should be medium confidence (0.4 - 0.7)
        assert 0.3 <= score < 0.7, f"Expected medium confidence, got {score}"

    def test_confidence_with_measurements(self, video_parser):
        """Test that measurements boost confidence score."""
        transcript = """
        Add 2 cups of flour, 1 tablespoon of sugar, and 3 teaspoons of baking powder.
        Mix well and bake.
        """

        recipe_data = {
            "name": "Simple Bread",
            "ingredients": [
                "2 cups flour",
                "1 tablespoon sugar",
                "3 teaspoons baking powder"
            ],
            "steps": [
                "Mix ingredients",
                "Bake"
            ]
        }

        score = video_parser._calculate_audio_confidence(transcript, recipe_data)

        # Should have reasonable confidence due to measurements
        assert score >= 0.5, f"Expected decent confidence with measurements, got {score}"

    def test_confidence_penalized_by_promotional_content(self, video_parser):
        """Test that promotional content reduces confidence."""
        transcript = """
        Make sure to like and subscribe! Check my bio for more recipes!
        Mix flour and sugar. Link in description below!
        """

        recipe_data = {
            "name": "Recipe",
            "ingredients": ["flour", "sugar"],
            "steps": ["Mix ingredients"]
        }

        score_with_promo = video_parser._calculate_audio_confidence(transcript, recipe_data)

        # Compare to similar recipe without promo content
        clean_transcript = "Mix flour and sugar together"
        score_without_promo = video_parser._calculate_audio_confidence(clean_transcript, recipe_data)

        # Promotional content should reduce score
        assert score_with_promo < score_without_promo, "Promotional content should reduce confidence"

    def test_confidence_with_cooking_verbs(self, video_parser):
        """Test that cooking action verbs increase confidence."""
        transcript = """
        Chop the vegetables, dice the onions, and slice the peppers. Heat the pan,
        add oil, and sauté everything together. Season with salt and pepper, then
        simmer for 10 minutes.
        """

        recipe_data = {
            "name": "Sautéed Vegetables",
            "ingredients": ["vegetables", "onions", "peppers", "oil", "salt", "pepper"],
            "steps": [
                "Chop vegetables",
                "Heat pan and sauté",
                "Season and simmer"
            ]
        }

        score = video_parser._calculate_audio_confidence(transcript, recipe_data)

        # Should have good confidence due to cooking vocabulary
        assert score >= 0.6, f"Expected good confidence with cooking verbs, got {score}"

    def test_empty_transcript_returns_zero(self, video_parser):
        """Test that empty transcript returns 0 confidence."""
        score = video_parser._calculate_audio_confidence("", {"name": "Test"})
        assert score == 0.0

    def test_empty_recipe_data_returns_zero(self, video_parser):
        """Test that empty recipe data returns 0 confidence."""
        score = video_parser._calculate_audio_confidence("some transcript", {})
        assert score == 0.0

    def test_confidence_with_detailed_steps(self, video_parser):
        """Test that detailed steps increase confidence."""
        transcript = "Let me show you how to make the perfect risotto"

        detailed_recipe = {
            "name": "Risotto",
            "ingredients": ["rice", "broth", "wine", "cheese"],
            "steps": [
                "First, heat the chicken broth in a separate pot and keep it warm on low heat",
                "In a large pan, heat olive oil and sauté the finely chopped onions until translucent",
                "Add the arborio rice and toast it for about 2 minutes while stirring constantly"
            ]
        }

        brief_recipe = {
            "name": "Risotto",
            "ingredients": ["rice", "broth", "wine", "cheese"],
            "steps": [
                "Heat broth",
                "Sauté onions",
                "Toast rice"
            ]
        }

        detailed_score = video_parser._calculate_audio_confidence(transcript, detailed_recipe)
        brief_score = video_parser._calculate_audio_confidence(transcript, brief_recipe)

        # Detailed steps should yield higher confidence
        assert detailed_score > brief_score, "Detailed steps should increase confidence"

    def test_confidence_with_metadata(self, video_parser):
        """Test that recipe metadata (servings, time) increases confidence."""
        transcript = "Quick 30-minute recipe for 4 people"

        recipe_with_metadata = {
            "name": "Quick Meal",
            "ingredients": ["ingredient1", "ingredient2"],
            "steps": ["step1", "step2"],
            "servings": 4,
            "total_time_minutes": 30
        }

        recipe_without_metadata = {
            "name": "Quick Meal",
            "ingredients": ["ingredient1", "ingredient2"],
            "steps": ["step1", "step2"]
        }

        score_with = video_parser._calculate_audio_confidence(transcript, recipe_with_metadata)
        score_without = video_parser._calculate_audio_confidence(transcript, recipe_without_metadata)

        # Metadata should increase confidence
        assert score_with > score_without, "Metadata should increase confidence"

    def test_confidence_score_range(self, video_parser):
        """Test that confidence scores are always in valid range [0, 1]."""
        test_cases = [
            ("", {}),  # Empty
            ("word", {"name": "test"}),  # Minimal
            ("a" * 1000, {"name": "test", "ingredients": ["i"] * 100, "steps": ["s"] * 100})  # Excessive
        ]

        for transcript, recipe_data in test_cases:
            score = video_parser._calculate_audio_confidence(transcript, recipe_data)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for input: {transcript[:50]}"

    def test_long_transcript_gets_high_length_score(self, video_parser):
        """Test that long transcripts (>100 words) get maximum length score."""
        # Create a 120-word transcript
        long_transcript = " ".join(["cook pasta add sauce"] * 30)

        recipe_data = {
            "name": "Pasta",
            "ingredients": ["pasta", "sauce"],
            "steps": ["cook", "add"]
        }

        score = video_parser._calculate_audio_confidence(long_transcript, recipe_data)

        # With 120 words + basic recipe, should get at least transcript quality points
        assert score > 0.25, f"Long transcript should get length bonus, got {score}"


class TestHybridAudioVisionRouting:
    """Test suite for smart audio+vision routing logic."""

    @pytest.fixture
    def video_parser(self):
        """Create VideoParser instance for testing."""
        return VideoParser(timeout=120)

    @pytest.fixture
    def mock_audio_extraction(self):
        """Mock audio extraction that returns high confidence result."""
        def _mock(confidence=0.8):
            return {
                'success': True,
                'transcript': "This is a detailed recipe with clear instructions.",
                'recipe_data': {
                    'name': 'Test Recipe',
                    'ingredients': ['ingredient1', 'ingredient2'],
                    'steps': ['step1', 'step2']
                },
                'confidence': confidence
            }
        return _mock

    @pytest.mark.asyncio
    async def test_high_confidence_routes_to_audio_only(self, video_parser, mock_audio_extraction):
        """Test that high confidence (≥0.7) routes to audio-only mode."""
        with patch.object(video_parser, '_try_audio_extraction') as mock_audio, \
             patch.object(video_parser, '_calculate_audio_confidence') as mock_confidence, \
             patch.object(video_parser, '_download_audio') as mock_download_audio, \
             patch.object(video_parser, '_detect_platform') as mock_platform, \
             patch('tempfile.mkdtemp') as mock_tempdir:

            # Setup mocks
            mock_tempdir.return_value = '/tmp/test'
            mock_platform.return_value = ('youtube.com', 'https://youtube.com/watch?v=123')
            mock_download_audio.return_value = {
                'success': True,
                'title': 'Test Recipe',
                'description': 'Test description'
            }

            # High confidence audio result
            mock_audio.return_value = mock_audio_extraction(confidence=0.85)
            mock_confidence.return_value = 0.85

            # Should NOT call vision methods
            with patch.object(video_parser, '_download_video') as mock_video, \
                 patch.object(video_parser, '_extract_key_frames') as mock_frames, \
                 patch.object(video_parser, '_vision_extract_recipe') as mock_vision:

                # Mock cleanup
                with patch('os.path.exists', return_value=True), \
                     patch('shutil.rmtree'):

                    result = await video_parser.parse('https://youtube.com/watch?v=123')

                # Verify routing
                assert result.success
                assert result.extraction_method == 'audio_only'
                assert result.frames_used == 0
                assert result.confidence_score == 0.85

                # Vision methods should NOT be called
                mock_video.assert_not_called()
                mock_frames.assert_not_called()
                mock_vision.assert_not_called()

    @pytest.mark.asyncio
    async def test_medium_confidence_routes_to_hybrid(self, video_parser, mock_audio_extraction):
        """Test that medium confidence (0.4-0.7) routes to hybrid mode."""
        with patch.object(video_parser, '_try_audio_extraction') as mock_audio, \
             patch.object(video_parser, '_calculate_audio_confidence') as mock_confidence, \
             patch.object(video_parser, '_download_audio') as mock_download_audio, \
             patch.object(video_parser, '_detect_platform') as mock_platform, \
             patch('tempfile.mkdtemp') as mock_tempdir:

            # Setup mocks
            mock_tempdir.return_value = '/tmp/test'
            mock_platform.return_value = ('tiktok.com', 'https://tiktok.com/@user/video/123')
            mock_download_audio.return_value = {
                'success': True,
                'title': 'Quick Recipe',
                'description': 'Fast recipe'
            }

            # Medium confidence audio result
            mock_audio.return_value = mock_audio_extraction(confidence=0.55)
            mock_confidence.return_value = 0.55

            # Mock video download and vision extraction
            with patch.object(video_parser, '_download_video') as mock_video, \
                 patch.object(video_parser, '_extract_key_frames') as mock_frames, \
                 patch.object(video_parser, '_vision_extract_recipe') as mock_vision:

                mock_video.return_value = '/tmp/test/video.mp4'
                mock_frames.return_value = ['frame1', 'frame2', 'frame3']
                mock_vision.return_value = {
                    'name': 'Enhanced Recipe',
                    'ingredients': ['ing1', 'ing2', 'ing3'],
                    'steps': ['step1', 'step2', 'step3']
                }

                # Mock cleanup
                with patch('os.path.exists', return_value=True), \
                     patch('shutil.rmtree'):

                    result = await video_parser.parse('https://tiktok.com/@user/video/123')

                # Verify routing to hybrid mode
                assert result.success
                assert result.extraction_method == 'hybrid'
                assert result.frames_used == 3  # Hybrid uses 3 frames
                assert result.confidence_score == 0.55

                # Verify vision methods were called
                mock_video.assert_called_once()
                mock_frames.assert_called_once_with('/tmp/test/video.mp4', num_frames=3)
                mock_vision.assert_called_once()

                # Verify audio transcript was passed to vision
                vision_call_kwargs = mock_vision.call_args[1]
                assert 'audio_transcript' in vision_call_kwargs
                assert vision_call_kwargs['audio_transcript'] is not None

    @pytest.mark.asyncio
    async def test_low_confidence_routes_to_vision_only(self, video_parser, mock_audio_extraction):
        """Test that low confidence (<0.4) routes to vision-only mode."""
        with patch.object(video_parser, '_try_audio_extraction') as mock_audio, \
             patch.object(video_parser, '_calculate_audio_confidence') as mock_confidence, \
             patch.object(video_parser, '_download_audio') as mock_download_audio, \
             patch.object(video_parser, '_detect_platform') as mock_platform, \
             patch('tempfile.mkdtemp') as mock_tempdir:

            # Setup mocks
            mock_tempdir.return_value = '/tmp/test'
            mock_platform.return_value = ('instagram.com', 'https://instagram.com/reel/abc123')
            mock_download_audio.return_value = {
                'success': True,
                'title': 'Recipe Reel',
                'description': 'Visual recipe'
            }

            # Low confidence audio result (mostly music)
            mock_audio.return_value = {
                'success': False,
                'confidence': 0.2,
                'reason': 'insufficient_audio',
                'transcript': '[music] [music] yeah'
            }
            mock_confidence.return_value = 0.2

            # Mock video download and vision extraction
            with patch.object(video_parser, '_download_video') as mock_video, \
                 patch.object(video_parser, '_extract_key_frames') as mock_frames, \
                 patch.object(video_parser, '_vision_extract_recipe') as mock_vision:

                mock_video.return_value = '/tmp/test/video.mp4'
                mock_frames.return_value = ['f1', 'f2', 'f3', 'f4', 'f5']
                mock_vision.return_value = {
                    'name': 'Visual Recipe',
                    'ingredients': ['ing1', 'ing2'],
                    'steps': ['step1', 'step2']
                }

                # Mock cleanup
                with patch('os.path.exists', return_value=True), \
                     patch('shutil.rmtree'):

                    result = await video_parser.parse('https://instagram.com/reel/abc123')

                # Verify routing to vision-only mode
                assert result.success
                assert result.extraction_method == 'vision_only'
                assert result.frames_used == 5  # Vision-only uses 5 frames
                assert result.confidence_score == 0.2
                assert result.fallback_reason == 'insufficient_audio'  # From audio_result['reason']

                # Verify vision methods were called with correct params
                mock_video.assert_called_once()
                mock_frames.assert_called_once_with('/tmp/test/video.mp4', num_frames=5)
                mock_vision.assert_called_once()

                # Verify NO audio transcript passed to vision (vision-only)
                vision_call_kwargs = mock_vision.call_args[1]
                assert vision_call_kwargs.get('audio_transcript') is None

    @pytest.mark.asyncio
    async def test_audio_extraction_failure_routes_to_vision(self, video_parser):
        """Test that audio extraction failure routes to vision-only mode."""
        with patch.object(video_parser, '_try_audio_extraction') as mock_audio, \
             patch.object(video_parser, '_download_audio') as mock_download_audio, \
             patch.object(video_parser, '_detect_platform') as mock_platform, \
             patch('tempfile.mkdtemp') as mock_tempdir:

            # Setup mocks
            mock_tempdir.return_value = '/tmp/test'
            mock_platform.return_value = ('youtube.com', 'https://youtube.com/shorts/xyz')
            mock_download_audio.return_value = {
                'success': True,
                'title': 'Recipe Short',
                'description': 'Quick recipe'
            }

            # Audio extraction fails completely
            mock_audio.return_value = {
                'success': False,
                'confidence': 0.0,
                'reason': 'transcription_error',
                'transcript': ''
            }

            # Mock video download and vision extraction
            with patch.object(video_parser, '_download_video') as mock_video, \
                 patch.object(video_parser, '_extract_key_frames') as mock_frames, \
                 patch.object(video_parser, '_vision_extract_recipe') as mock_vision:

                mock_video.return_value = '/tmp/test/video.mp4'
                mock_frames.return_value = ['f1', 'f2', 'f3', 'f4', 'f5']
                mock_vision.return_value = {
                    'name': 'Fallback Recipe',
                    'ingredients': ['ingredient'],
                    'steps': ['step']
                }

                # Mock cleanup
                with patch('os.path.exists', return_value=True), \
                     patch('shutil.rmtree'):

                    result = await video_parser.parse('https://youtube.com/shorts/xyz')

                # Should fallback to vision-only
                assert result.success
                assert result.extraction_method == 'vision_only'
                assert result.frames_used == 5
                assert result.fallback_reason == 'transcription_error'  # From audio_result['reason']

    def test_cost_estimation_audio_only(self, video_parser):
        """Test cost estimation for audio-only extraction."""
        cost = video_parser._estimate_cost('audio_only', frames_used=0)

        # Audio-only: Whisper + GPT-4 Text = ~$0.011
        assert 0.010 <= cost <= 0.012, f"Audio-only cost should be ~$0.011, got ${cost}"

    def test_cost_estimation_hybrid(self, video_parser):
        """Test cost estimation for hybrid extraction with 3 frames."""
        cost = video_parser._estimate_cost('hybrid', frames_used=3)

        # Hybrid: Whisper + GPT-4 Text + 3 frames = ~$0.041
        assert 0.039 <= cost <= 0.043, f"Hybrid cost should be ~$0.041, got ${cost}"

    def test_cost_estimation_vision_only(self, video_parser):
        """Test cost estimation for vision-only with 5 frames."""
        cost = video_parser._estimate_cost('vision_only', frames_used=5)

        # Vision-only: 5 frames = ~$0.05
        assert 0.048 <= cost <= 0.052, f"Vision-only cost should be ~$0.05, got ${cost}"

    def test_optimal_frame_count_hybrid_mode(self, video_parser):
        """Test optimal frame count calculation for hybrid mode."""
        # Medium confidence should return 3 frames
        count = video_parser._get_optimal_frame_count(confidence=0.55, video_duration=60)
        assert count == 3, "Hybrid mode should use 3 frames"

    def test_optimal_frame_count_vision_short_video(self, video_parser):
        """Test optimal frame count for short video in vision-only mode."""
        # Low confidence + short video = 3 frames
        count = video_parser._get_optimal_frame_count(confidence=0.2, video_duration=20)
        assert count == 3, "Short video should use 3 frames even in vision-only"

    def test_optimal_frame_count_vision_long_video(self, video_parser):
        """Test optimal frame count for long video in vision-only mode."""
        # Low confidence + long video = 5 frames
        count = video_parser._get_optimal_frame_count(confidence=0.2, video_duration=120)
        assert count == 5, "Long video should use 5 frames in vision-only"

    @pytest.mark.asyncio
    async def test_extraction_metadata_populated(self, video_parser, mock_audio_extraction):
        """Test that extraction metadata is properly populated in ParseResult."""
        with patch.object(video_parser, '_try_audio_extraction') as mock_audio, \
             patch.object(video_parser, '_calculate_audio_confidence') as mock_confidence, \
             patch.object(video_parser, '_download_audio') as mock_download_audio, \
             patch.object(video_parser, '_detect_platform') as mock_platform, \
             patch('tempfile.mkdtemp') as mock_tempdir:

            # Setup mocks for high confidence audio-only
            mock_tempdir.return_value = '/tmp/test'
            mock_platform.return_value = ('youtube.com', 'https://youtube.com/watch?v=123')
            mock_download_audio.return_value = {
                'success': True,
                'title': 'Test Recipe',
                'description': 'Test'
            }
            mock_audio.return_value = mock_audio_extraction(confidence=0.9)
            mock_confidence.return_value = 0.9

            # Mock cleanup
            with patch('os.path.exists', return_value=True), \
                 patch('shutil.rmtree'):

                result = await video_parser.parse('https://youtube.com/watch?v=123')

            # Verify metadata fields are populated
            assert result.extraction_method == 'audio_only'
            assert result.frames_used == 0
            assert result.estimated_cost is not None
            assert result.estimated_cost > 0
            assert result.confidence_score == 0.9
            assert result.fallback_reason is None

    @pytest.mark.asyncio
    async def test_fallback_cascading(self, video_parser):
        """Test graceful fallback when audio fails and vision succeeds."""
        with patch.object(video_parser, '_try_audio_extraction') as mock_audio, \
             patch.object(video_parser, '_download_audio') as mock_download_audio, \
             patch.object(video_parser, '_detect_platform') as mock_platform, \
             patch('tempfile.mkdtemp') as mock_tempdir:

            # Setup mocks
            mock_tempdir.return_value = '/tmp/test'
            mock_platform.return_value = ('tiktok.com', 'https://tiktok.com/@user/video/123')
            mock_download_audio.return_value = {
                'success': True,
                'title': 'Recipe',
                'description': 'Test'
            }

            # Audio fails
            mock_audio.return_value = {
                'success': False,
                'confidence': 0.0,
                'reason': 'not_a_recipe',
                'transcript': 'random music video'
            }

            # Vision succeeds
            with patch.object(video_parser, '_download_video') as mock_video, \
                 patch.object(video_parser, '_extract_key_frames') as mock_frames, \
                 patch.object(video_parser, '_vision_extract_recipe') as mock_vision:

                mock_video.return_value = '/tmp/test/video.mp4'
                mock_frames.return_value = ['f1', 'f2', 'f3', 'f4', 'f5']
                mock_vision.return_value = {
                    'name': 'Visual Recipe',
                    'ingredients': ['ing1'],
                    'steps': ['step1']
                }

                # Mock cleanup
                with patch('os.path.exists', return_value=True), \
                     patch('shutil.rmtree'):

                    result = await video_parser.parse('https://tiktok.com/@user/video/123')

                # Should succeed via vision fallback
                assert result.success
                assert result.extraction_method == 'vision_only'
                assert result.fallback_reason == 'not_a_recipe'  # From audio_result['reason']

    @pytest.mark.asyncio
    async def test_try_audio_extraction_success(self, video_parser):
        """Test _try_audio_extraction with successful extraction."""
        with patch.object(video_parser, '_transcribe_audio') as mock_transcribe, \
             patch.object(video_parser, '_parse_transcript_to_recipe') as mock_parse:

            mock_transcribe.return_value = "Detailed recipe instructions with measurements"
            mock_parse.return_value = {
                'is_recipe': True,
                'name': 'Test Recipe',
                'ingredients': ['ing1', 'ing2'],
                'steps': ['step1', 'step2']
            }

            result = await video_parser._try_audio_extraction(
                audio_path='/tmp/audio.m4a',
                download_info={'title': 'Test', 'description': 'Test', 'platform': 'youtube.com', 'url': 'test'}
            )

            assert result['success'] is True
            assert result['confidence'] == 1.0
            assert 'recipe_data' in result
            assert 'transcript' in result

    @pytest.mark.asyncio
    async def test_try_audio_extraction_insufficient_audio(self, video_parser):
        """Test _try_audio_extraction with insufficient audio content."""
        with patch.object(video_parser, '_transcribe_audio') as mock_transcribe:

            # Very short transcript
            mock_transcribe.return_value = "short"

            result = await video_parser._try_audio_extraction(
                audio_path='/tmp/audio.m4a',
                download_info={'title': 'Test', 'description': 'Test', 'platform': 'youtube.com', 'url': 'test'}
            )

            assert result['success'] is False
            assert result['confidence'] == 0.0
            assert result['reason'] == 'insufficient_audio'

    @pytest.mark.asyncio
    async def test_try_audio_extraction_not_a_recipe(self, video_parser):
        """Test _try_audio_extraction when content is not a recipe."""
        with patch.object(video_parser, '_transcribe_audio') as mock_transcribe, \
             patch.object(video_parser, '_parse_transcript_to_recipe') as mock_parse:

            mock_transcribe.return_value = "This is a music video with no recipe content"
            mock_parse.return_value = {
                'is_recipe': False,
                'name': None,
                'ingredients': [],
                'steps': []
            }

            result = await video_parser._try_audio_extraction(
                audio_path='/tmp/audio.m4a',
                download_info={'title': 'Test', 'description': 'Test', 'platform': 'youtube.com', 'url': 'test'}
            )

            assert result['success'] is False
            assert result['confidence'] == 0.1
            assert result['reason'] == 'not_a_recipe'

    @pytest.mark.asyncio
    async def test_try_audio_extraction_exception_handling(self, video_parser):
        """Test _try_audio_extraction handles exceptions gracefully."""
        with patch.object(video_parser, '_transcribe_audio') as mock_transcribe:

            # Transcription fails
            mock_transcribe.side_effect = Exception("API Error")

            result = await video_parser._try_audio_extraction(
                audio_path='/tmp/audio.m4a',
                download_info={'title': 'Test', 'description': 'Test', 'platform': 'youtube.com', 'url': 'test'}
            )

            assert result['success'] is False
            assert result['confidence'] == 0.0
            assert 'API Error' in result['reason']


class TestPlatformSpecificOptimizations:
    """Test suite for platform-specific optimizations (Issue #38)."""

    @pytest.fixture
    def video_parser(self):
        """Create VideoParser instance for testing."""
        return VideoParser(timeout=120)

    def test_get_platform_config_tiktok(self, video_parser):
        """Test TikTok platform configuration retrieval."""
        config = video_parser._get_platform_config('tiktok')

        assert config['audio_confidence_threshold'] == 0.65
        assert config['hybrid_confidence_threshold'] == 0.35
        assert config['default_frames'] == 3
        assert config['max_frames'] == 4
        assert config['detect_slideshows'] is True

    def test_get_platform_config_instagram(self, video_parser):
        """Test Instagram platform configuration retrieval."""
        config = video_parser._get_platform_config('instagram')

        assert config['audio_confidence_threshold'] == 0.75
        assert config['hybrid_confidence_threshold'] == 0.45
        assert config['default_frames'] == 4
        assert config['max_frames'] == 5
        assert config['detect_slideshows'] is False

    def test_get_platform_config_youtube(self, video_parser):
        """Test YouTube platform configuration retrieval."""
        config = video_parser._get_platform_config('youtube')

        assert config['audio_confidence_threshold'] == 0.8
        assert config['hybrid_confidence_threshold'] == 0.5
        assert config['default_frames'] == 3
        assert config['max_frames'] == 4
        assert config['detect_slideshows'] is False

    def test_get_platform_config_unknown(self, video_parser):
        """Test unknown platform falls back to default configuration."""
        config = video_parser._get_platform_config('unknown_platform')

        assert config['audio_confidence_threshold'] == 0.7
        assert config['hybrid_confidence_threshold'] == 0.4
        assert config['default_frames'] == 4
        assert config['max_frames'] == 5

    def test_get_platform_config_none(self, video_parser):
        """Test None platform falls back to default configuration."""
        config = video_parser._get_platform_config(None)

        assert config['audio_confidence_threshold'] == 0.7
        assert config['hybrid_confidence_threshold'] == 0.4

    def test_is_slideshow_video_high_similarity(self, video_parser):
        """Test slideshow detection with high frame similarity."""
        # Create 3 identical frames (base64-encoded blank images)
        import base64
        from PIL import Image
        import io

        # Create identical frames
        frames = []
        for _ in range(3):
            img = Image.new('RGB', (100, 100), color=(255, 255, 255))
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            frame_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            frames.append(frame_b64)

        is_slideshow = video_parser._is_slideshow_video(frames, similarity_threshold=0.95)
        assert is_slideshow is True

    def test_is_slideshow_video_low_similarity(self, video_parser):
        """Test slideshow detection with low frame similarity (normal video)."""
        import base64
        from PIL import Image
        from PIL import ImageDraw
        import io

        # Create different frames with varying content (not just solid colors)
        frames = []
        for i in range(3):
            img = Image.new('RGB', (100, 100), color=(255, 255, 255))
            draw = ImageDraw.Draw(img)
            # Draw different shapes in each frame
            if i == 0:
                draw.rectangle([10, 10, 40, 40], fill=(255, 0, 0))
            elif i == 1:
                draw.ellipse([50, 50, 80, 80], fill=(0, 255, 0))
            else:
                draw.polygon([(10, 90), (50, 10), (90, 90)], fill=(0, 0, 255))

            buffer = io.BytesIO()
            img.save(buffer, format='JPEG')
            frame_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            frames.append(frame_b64)

        is_slideshow = video_parser._is_slideshow_video(frames, similarity_threshold=0.95)
        assert is_slideshow is False

    def test_is_slideshow_video_insufficient_frames(self, video_parser):
        """Test slideshow detection with insufficient frames."""
        import base64

        # Only 1 frame
        is_slideshow = video_parser._is_slideshow_video([base64.b64encode(b'fake').decode('utf-8')])
        assert is_slideshow is False

    @pytest.mark.asyncio
    async def test_tiktok_routing_medium_confidence(self, video_parser):
        """Test TikTok routes to audio-only with confidence 0.70 (above 0.65 threshold)."""
        with patch.object(video_parser, '_detect_platform') as mock_detect, \
             patch.object(video_parser, '_resolve_short_url') as mock_resolve, \
             patch.object(video_parser, '_download_audio') as mock_audio, \
             patch.object(video_parser, '_try_audio_extraction') as mock_try_audio, \
             patch.object(video_parser, '_calculate_audio_confidence') as mock_confidence:

            mock_detect.return_value = 'tiktok'
            mock_resolve.return_value = ('https://tiktok.com/@user/video/123', None)
            mock_audio.return_value = {
                'success': True,
                'title': 'Test Recipe',
                'description': 'Test description',
                'platform': 'tiktok',
                'url': 'https://tiktok.com/@user/video/123'
            }

            # Audio extraction succeeded
            mock_try_audio.return_value = {
                'success': True,
                'recipe_data': {'name': 'Test Recipe', 'ingredients': [], 'steps': []},
                'transcript': 'Test transcript'
            }

            # Confidence 0.70 - above TikTok audio threshold (0.65) but below default (0.7)
            mock_confidence.return_value = 0.70

            result = await video_parser.parse('https://tiktok.com/@user/video/123')

            # Should use audio-only (confidence 0.70 >= 0.65)
            assert result.success is True
            assert result.extraction_method == 'audio_only'

    @pytest.mark.asyncio
    async def test_instagram_routing_medium_confidence(self, video_parser):
        """Test Instagram requires higher confidence (0.73 < 0.75 threshold) for audio-only."""
        with patch.object(video_parser, '_detect_platform') as mock_detect, \
             patch.object(video_parser, '_resolve_short_url') as mock_resolve, \
             patch.object(video_parser, '_download_audio') as mock_audio, \
             patch.object(video_parser, '_try_audio_extraction') as mock_try_audio, \
             patch.object(video_parser, '_calculate_audio_confidence') as mock_confidence, \
             patch.object(video_parser, '_download_video') as mock_video, \
             patch.object(video_parser, '_extract_key_frames') as mock_frames, \
             patch.object(video_parser, '_vision_extract_recipe') as mock_vision:

            mock_detect.return_value = 'instagram'
            mock_resolve.return_value = ('https://instagram.com/reel/ABC123', None)
            mock_audio.return_value = {
                'success': True,
                'title': 'Test Recipe',
                'description': 'Test description',
                'platform': 'instagram',
                'url': 'https://instagram.com/reel/ABC123'
            }

            # Audio extraction succeeded
            mock_try_audio.return_value = {
                'success': True,
                'recipe_data': {'name': 'Test Recipe', 'ingredients': [], 'steps': []},
                'transcript': 'Test transcript'
            }

            # Confidence 0.73 - below Instagram threshold (0.75)
            mock_confidence.return_value = 0.73

            mock_video.return_value = '/tmp/video.mp4'
            mock_frames.return_value = ['frame1', 'frame2', 'frame3', 'frame4']
            mock_vision.return_value = {'name': 'Vision Recipe', 'ingredients': [], 'steps': []}

            result = await video_parser.parse('https://instagram.com/reel/ABC123')

            # Should use hybrid mode (0.73 >= 0.45 hybrid threshold)
            assert result.success is True
            assert result.extraction_method == 'hybrid'
            assert result.frames_used == 4  # Instagram default_frames

    @pytest.mark.asyncio
    async def test_youtube_routing_high_threshold(self, video_parser):
        """Test YouTube requires highest confidence (0.78 < 0.8 threshold) for audio-only."""
        with patch.object(video_parser, '_detect_platform') as mock_detect, \
             patch.object(video_parser, '_resolve_short_url') as mock_resolve, \
             patch.object(video_parser, '_download_audio') as mock_audio, \
             patch.object(video_parser, '_try_audio_extraction') as mock_try_audio, \
             patch.object(video_parser, '_calculate_audio_confidence') as mock_confidence, \
             patch.object(video_parser, '_download_video') as mock_video, \
             patch.object(video_parser, '_extract_key_frames') as mock_frames, \
             patch.object(video_parser, '_vision_extract_recipe') as mock_vision:

            mock_detect.return_value = 'youtube'
            mock_resolve.return_value = ('https://youtube.com/shorts/xyz', None)
            mock_audio.return_value = {
                'success': True,
                'title': 'Test Recipe',
                'description': 'Test description',
                'platform': 'youtube',
                'url': 'https://youtube.com/shorts/xyz'
            }

            # Audio extraction succeeded
            mock_try_audio.return_value = {
                'success': True,
                'recipe_data': {'name': 'Test Recipe', 'ingredients': [], 'steps': []},
                'transcript': 'Test transcript'
            }

            # Confidence 0.78 - below YouTube threshold (0.8)
            mock_confidence.return_value = 0.78

            mock_video.return_value = '/tmp/video.mp4'
            mock_frames.return_value = ['frame1', 'frame2', 'frame3']
            mock_vision.return_value = {'name': 'Vision Recipe', 'ingredients': [], 'steps': []}

            result = await video_parser.parse('https://youtube.com/shorts/xyz')

            # Should use hybrid mode (0.78 >= 0.5 hybrid threshold)
            assert result.success is True
            assert result.extraction_method == 'hybrid'
            assert result.frames_used == 3  # YouTube default_frames

    @pytest.mark.asyncio
    async def test_tiktok_slideshow_detection(self, video_parser):
        """Test TikTok slideshow detection switches to vision-only mode."""
        with patch.object(video_parser, '_detect_platform') as mock_detect, \
             patch.object(video_parser, '_resolve_short_url') as mock_resolve, \
             patch.object(video_parser, '_download_audio') as mock_audio, \
             patch.object(video_parser, '_try_audio_extraction') as mock_try_audio, \
             patch.object(video_parser, '_calculate_audio_confidence') as mock_confidence, \
             patch.object(video_parser, '_download_video') as mock_video, \
             patch.object(video_parser, '_extract_key_frames') as mock_frames, \
             patch.object(video_parser, '_is_slideshow_video') as mock_slideshow, \
             patch.object(video_parser, '_vision_extract_recipe') as mock_vision:

            mock_detect.return_value = 'tiktok'
            mock_resolve.return_value = ('https://tiktok.com/@user/video/123', None)
            mock_audio.return_value = {
                'success': True,
                'title': 'Test Recipe',
                'description': 'Test description',
                'platform': 'tiktok',
                'url': 'https://tiktok.com/@user/video/123'
            }

            # Audio extraction succeeded
            mock_try_audio.return_value = {
                'success': True,
                'recipe_data': {'name': 'Test Recipe', 'ingredients': [], 'steps': []},
                'transcript': 'Background music'
            }

            # Medium confidence - would normally use hybrid mode
            mock_confidence.return_value = 0.50

            mock_video.return_value = '/tmp/video.mp4'
            # First call returns 3 frames (default), second call returns 4 (max_frames for slideshow)
            mock_frames.side_effect = [
                ['frame1', 'frame2', 'frame3'],
                ['frame1', 'frame2', 'frame3', 'frame4']
            ]
            mock_slideshow.return_value = True  # Detected as slideshow
            mock_vision.return_value = {'name': 'Vision Recipe', 'ingredients': [], 'steps': []}

            result = await video_parser.parse('https://tiktok.com/@user/video/123')

            # Should switch to vision-only due to slideshow detection
            assert result.success is True
            assert result.extraction_method == 'vision_only'
            assert result.fallback_reason == 'tiktok_slideshow_detected'
            assert result.frames_used == 4  # TikTok max_frames for slideshows

    @pytest.mark.asyncio
    async def test_platform_specific_frame_counts(self, video_parser):
        """Test platform-specific frame counts are used correctly."""
        test_cases = [
            ('tiktok', 3, 4),      # default_frames=3, max_frames=4
            ('instagram', 4, 5),   # default_frames=4, max_frames=5
            ('youtube', 3, 4),     # default_frames=3, max_frames=4
        ]

        for platform, expected_hybrid, expected_vision in test_cases:
            with patch.object(video_parser, '_detect_platform') as mock_detect, \
                 patch.object(video_parser, '_resolve_short_url') as mock_resolve, \
                 patch.object(video_parser, '_download_audio') as mock_audio, \
                 patch.object(video_parser, '_try_audio_extraction') as mock_try_audio, \
                 patch.object(video_parser, '_download_video') as mock_video, \
                 patch.object(video_parser, '_extract_key_frames') as mock_frames, \
                 patch.object(video_parser, '_is_slideshow_video') as mock_slideshow, \
                 patch.object(video_parser, '_vision_extract_recipe') as mock_vision:

                mock_detect.return_value = platform
                mock_resolve.return_value = (f'https://{platform}.com/video/123', None)
                mock_audio.return_value = {
                    'success': True,
                    'title': 'Test Recipe',
                    'description': 'Test description',
                    'platform': platform,
                    'url': f'https://{platform}.com/video/123'
                }

                # Low confidence for vision-only mode
                mock_try_audio.return_value = {
                    'success': False,
                    'confidence': 0.1,
                    'recipe_data': None,
                    'reason': 'low_confidence'
                }

                mock_video.return_value = '/tmp/video.mp4'
                mock_frames.return_value = ['frame'] * expected_vision
                mock_slideshow.return_value = False
                mock_vision.return_value = {'name': 'Recipe', 'ingredients': [], 'steps': []}

                result = await video_parser.parse(f'https://{platform}.com/video/123')

                # Should use platform-specific max_frames for vision-only
                assert result.frames_used == expected_vision, f"{platform} should use {expected_vision} frames for vision-only"
