"""
Video recipe parser for TikTok, Instagram Reels, and YouTube Shorts.
Uses audio-first approach: Download video → Extract audio → Whisper → GPT-4 recipe parsing.
"""
import os
import re
import time
import json
import tempfile
import subprocess
import logging
import requests
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from parsers.base import BaseParser, ParseResult
from app.security import is_safe_url

logger = logging.getLogger(__name__)


class VideoParser(BaseParser):
    """
    Parse recipes from video URLs (TikTok, Instagram Reels, YouTube Shorts).
    
    Pipeline:
    1. Download video with yt-dlp
    2. Extract audio with ffmpeg
    3. Transcribe with OpenAI Whisper
    4. Parse transcript with GPT-4 to extract structured recipe
    """

    # URL patterns for supported platforms
    TIKTOK_PATTERNS = [
        r'(tiktok\.com/@[\w.]+/video/\d+)',
        r'(tiktok\.com/t/[\w]+)',
        r'(vm\.tiktok\.com/[\w]+)',
    ]
    
    INSTAGRAM_PATTERNS = [
        r'(instagram\.com/reel/[\w-]+)',
        r'(instagram\.com/reels/[\w-]+)',
        r'(instagram\.com/p/[\w-]+)',  # Also handle posts with videos
    ]
    
    YOUTUBE_PATTERNS = [
        r'(youtube\.com/shorts/[\w-]+)',
        r'(youtu\.be/[\w-]+)',
        r'(youtube\.com/watch\?v=[\w-]+)',
    ]

    FACEBOOK_PATTERNS = [
        r'(facebook\.com/[\w.\-]+/videos/[\w\-/]+)',  # page/videos/[slug/]id
        r'(facebook\.com/watch/?\?v=\d+)',            # watch?v=ID
        r'(facebook\.com/reel/\d+)',                  # reels
        r'(facebook\.com/share/[vr]/[\w-]+)',         # share/v/ or share/r/ links
        r'(fb\.watch/[\w-]+)',                        # short links
    ]

    # Platform-specific optimization configurations
    PLATFORM_CONFIG = {
        'tiktok': {
            'audio_confidence_threshold': 0.65,  # Slightly lower - often has music
            'hybrid_confidence_threshold': 0.35,  # Lower threshold for hybrid
            'default_frames': 3,  # Shorter videos
            'max_frames': 4,
            'detect_slideshows': True,  # Check for picture slideshows
            'prompt_hints': 'TikTok videos often have text overlays with ingredients and steps. Pay special attention to on-screen text.',
        },
        'instagram': {
            'audio_confidence_threshold': 0.75,  # Higher - better audio quality
            'hybrid_confidence_threshold': 0.45,
            'default_frames': 4,  # Medium-length videos
            'max_frames': 5,
            'detect_slideshows': False,  # Less common
            'prompt_hints': 'Instagram Reels often have clear voiceovers and aesthetic visuals. Look for captions/subtitles.',
        },
        'youtube': {
            'audio_confidence_threshold': 0.8,  # Highest - best audio quality
            'hybrid_confidence_threshold': 0.5,
            'default_frames': 3,  # Prefer audio, fewer frames needed
            'max_frames': 4,
            'detect_slideshows': False,  # Rare
            'prompt_hints': 'YouTube Shorts typically have professional production and detailed explanations.',
        },
        'facebook': {
            'audio_confidence_threshold': 0.75,  # Similar profile to Instagram Reels
            'hybrid_confidence_threshold': 0.45,
            'default_frames': 4,
            'max_frames': 5,
            'detect_slideshows': False,
            'prompt_hints': 'Facebook recipe videos often have voiceovers plus on-screen captions/text overlays. Read any visible text for ingredients and steps.',
        },
        'default': {
            'audio_confidence_threshold': 0.7,
            'hybrid_confidence_threshold': 0.4,
            'default_frames': 4,
            'max_frames': 5,
            'detect_slideshows': False,
            'prompt_hints': '',
        }
    }

    # Path to cookies file for authenticated downloads (bypasses IP blocks)
    COOKIES_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'tiktok_cookies.txt')


    def __init__(self, timeout: int = 120, openai_client=None):
        """
        Initialize video parser.

        Args:
            timeout: Maximum time for video download/processing
            openai_client: Optional OpenAI client (lazy-loaded if not provided)
        """
        super().__init__(timeout)
        self.parser_name = "video-audio-parser"
        self._openai_client = openai_client

    def _ytdlp_base_args(self) -> list:
        """Build common yt-dlp args with cookies, impersonation, and proxy for TikTok."""
        args = ['yt-dlp']
        # Use cookies file if it exists (needed to bypass TikTok IP blocks)
        if os.path.exists(self.COOKIES_FILE):
            args.extend(['--cookies', self.COOKIES_FILE])
        # Use proxy if configured (needed for datacenter IPs blocked by TikTok)
        proxy = os.environ.get('YTDLP_PROXY')
        if proxy:
            args.extend(['--proxy', proxy])
        # Impersonate a real browser to avoid bot detection — but ONLY if explicitly
        # enabled. The standalone yt-dlp release binary ships without curl_cffi and
        # hard-fails on --impersonate before any download (breaking Instagram/Facebook/
        # YouTube). It also still *lists* "chrome" via --list-impersonate-targets even
        # though it can't use it, so we can't probe for support — we require an explicit
        # opt-in via YTDLP_IMPERSONATE=1 (set only on a curl_cffi-capable yt-dlp).
        if self._impersonation_available():
            args.extend(['--impersonate', 'chrome'])
        return args

    @classmethod
    def _impersonation_available(cls) -> bool:
        """Whether to pass --impersonate to yt-dlp.

        Opt-in only: the standalone release binary lists impersonate targets but
        can't actually use them (no curl_cffi), so probing is unreliable. Enable
        explicitly with YTDLP_IMPERSONATE=1 on an impersonation-capable yt-dlp.
        Default off → plain (non-impersonated) download, which works for public
        Instagram/Facebook/YouTube videos instead of crashing the ingestion.
        """
        return os.environ.get('YTDLP_IMPERSONATE', '').strip().lower() in ('1', 'true', 'yes')

    @property
    def openai_client(self):
        """Lazy load OpenAI client."""
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI()
        return self._openai_client

    async def validate_url(self, url: str) -> bool:
        """Check if URL is a supported video platform and safe from SSRF."""
        is_safe, reason = is_safe_url(url)
        if not is_safe:
            logger.warning(f"URL blocked by SSRF check: {url} - {reason}")
            return False
        return self._detect_platform(url) is not None
    
    def _detect_platform(self, url: str) -> Optional[str]:
        """
        Detect which platform the URL belongs to.

        Returns: 'tiktok', 'instagram', 'youtube', 'facebook', or None
        """
        url_lower = url.lower()

        for pattern in self.TIKTOK_PATTERNS:
            if re.search(pattern, url_lower):
                return 'tiktok'

        for pattern in self.INSTAGRAM_PATTERNS:
            if re.search(pattern, url_lower):
                return 'instagram'

        for pattern in self.YOUTUBE_PATTERNS:
            if re.search(pattern, url_lower):
                return 'youtube'

        for pattern in self.FACEBOOK_PATTERNS:
            if re.search(pattern, url_lower):
                return 'facebook'

        return None

    def _get_platform_config(self, platform: Optional[str]) -> Dict[str, Any]:
        """
        Get platform-specific configuration.

        Args:
            platform: Platform name ('tiktok', 'instagram', 'youtube') or None

        Returns:
            Platform configuration dict with thresholds and settings
        """
        if platform and platform in self.PLATFORM_CONFIG:
            return self.PLATFORM_CONFIG[platform]
        return self.PLATFORM_CONFIG['default']

    def _is_slideshow_video(self, frames: List[str], similarity_threshold: float = 0.95) -> bool:
        """
        Detect if video is a picture slideshow (common on TikTok).

        Picture slideshows have very high frame similarity since they're static images
        with transitions, versus actual video which has continuous motion.

        Args:
            frames: List of base64-encoded frame images
            similarity_threshold: Frames above this similarity are considered identical (0.95 = 95%)

        Returns:
            True if video appears to be a slideshow (high frame similarity)
        """
        if len(frames) < 2:
            return False

        # Decode frames and compute hashes
        from PIL import Image
        import io
        import base64

        hashes = []
        for frame_b64 in frames:
            try:
                # Decode base64 to image
                frame_bytes = base64.b64decode(frame_b64)
                img = Image.open(io.BytesIO(frame_bytes))

                # Compute perceptual hash (same as _compute_frame_hash)
                img = img.convert('L').resize((9, 8), Image.Resampling.LANCZOS)
                pixels = list(img.getdata())

                avg = sum(pixels) / len(pixels)
                bits = ''.join('1' if p > avg else '0' for p in pixels)
                hashes.append(bits)
            except Exception as e:
                logger.warning(f"Failed to hash frame for slideshow detection: {e}")
                continue

        if len(hashes) < 2:
            return False

        # Calculate average similarity between consecutive frames
        similarities = []
        for i in range(len(hashes) - 1):
            # Hamming distance
            diff = sum(c1 != c2 for c1, c2 in zip(hashes[i], hashes[i+1]))
            similarity = 1.0 - (diff / len(hashes[i]))
            similarities.append(similarity)

        avg_similarity = sum(similarities) / len(similarities)

        is_slideshow = avg_similarity >= similarity_threshold
        logger.info(f"Slideshow detection: avg_similarity={avg_similarity:.3f}, threshold={similarity_threshold:.3f}, is_slideshow={is_slideshow}")

        return is_slideshow

    def _resolve_short_url(self, url: str, platform: str) -> tuple[str, Optional[str]]:
        """
        Resolve short/redirect URLs to their final destination.
        
        TikTok short URLs like /t/... or vm.tiktok.com/... redirect to the actual video URL.
        This is needed because yt-dlp sometimes doesn't follow these redirects properly.
        
        Args:
            url: The short URL to resolve
            platform: The detected platform
            
        Returns:
            Tuple of (resolved_url, error_message). If error_message is set, the URL is invalid.
        """
        # NOTE: We no longer manually resolve short URLs because TikTok's anti-bot
        # measures make manual resolution unreliable (redirects to homepage).
        # Instead, we let yt-dlp handle resolution natively, as it has much better
        # anti-bot capabilities and can handle short URLs directly.

        short_patterns = [
            r'tiktok\.com/t/',
            r'vm\.tiktok\.com/',
        ]

        is_short_url = any(re.search(p, url.lower()) for p in short_patterns)

        if is_short_url:
            logger.info(f"Short URL detected: {url} - yt-dlp will handle resolution")

        # Always return original URL and let yt-dlp resolve it
        return (url, None)

    async def parse(self, url: str, **kwargs) -> ParseResult:
        """
        Parse a recipe from a video URL using smart audio+vision routing.

        Pipeline:
        1. Detect platform and download audio (always - it's cheap)
        2. Try audio-only extraction with Whisper + GPT-4
        3. Calculate audio confidence score
        4. Route based on confidence:
           - High (≥0.7): Use audio result (cost-efficient)
           - Medium (0.4-0.7): Enhance with 3 vision frames (hybrid)
           - Low (<0.4): Full vision with 5 frames (vision-only)

        Args:
            url: Video URL (TikTok, Instagram, YouTube)
            **kwargs: Additional options
                - force_mode: str - Force specific mode: "audio", "hybrid", "vision"

        Returns:
            ParseResult with recipe data and extraction metadata
        """
        start_time = time.time()
        temp_dir = None
        force_mode = kwargs.get('force_mode', None)

        try:
            # Step 1: Detect platform
            platform = self._detect_platform(url)
            if not platform:
                return ParseResult(
                    success=False,
                    error_code="UNSUPPORTED_PLATFORM",
                    error_message=f"URL not recognized as TikTok, Instagram, YouTube, or Facebook: {url}",
                    parser_name=self.parser_name
                )

            logger.info(f"Detected platform: {platform} for URL: {url}")

            # Resolve short URLs
            resolved_url, resolution_error = self._resolve_short_url(url, platform)

            if resolution_error:
                return ParseResult(
                    success=False,
                    error_code="EXPIRED_SHORT_URL",
                    error_message=resolution_error,
                    parser_name=self.parser_name
                )

            if resolved_url != url:
                logger.info(f"Using resolved URL: {resolved_url}")

            # Create temp directory
            temp_dir = tempfile.mkdtemp(prefix="video_recipe_")
            audio_path = os.path.join(temp_dir, "audio.mp3")
            tikwm_metadata = None

            # Step 2: Download audio
            if platform == 'tiktok':
                # TikTok: Use TikWM API instead of yt-dlp
                logger.info("Fetching TikTok metadata via TikWM...")
                tikwm_metadata = self._fetch_tiktok_metadata_via_tikwm(url)

                if not tikwm_metadata.get('success'):
                    return ParseResult(
                        success=False,
                        error_code="TIKWM_FAILED",
                        error_message=tikwm_metadata.get('error', 'TikWM metadata fetch failed'),
                        parser_name=self.parser_name
                    )

                # Download audio from TikWM CDN URL
                audio_url = tikwm_metadata.get('audio_url', '')
                if not audio_url:
                    return ParseResult(
                        success=False,
                        error_code="TIKWM_NO_AUDIO",
                        error_message="TikWM did not return an audio URL",
                        parser_name=self.parser_name
                    )

                logger.info("Downloading TikTok audio from TikWM CDN...")
                audio_download = self._download_from_url(audio_url, audio_path)

                if not audio_download.get('success'):
                    return ParseResult(
                        success=False,
                        error_code="DOWNLOAD_FAILED",
                        error_message=audio_download.get('error', 'Failed to download TikTok audio'),
                        parser_name=self.parser_name
                    )

                download_info = {
                    'success': True,
                    'title': tikwm_metadata.get('title', ''),
                    'description': tikwm_metadata.get('description', ''),
                    'duration': tikwm_metadata.get('duration', 0),
                    'file_size': os.path.getsize(audio_path) if os.path.exists(audio_path) else 0,
                }
            else:
                # Instagram/YouTube: Use yt-dlp as before
                logger.info("Downloading audio with yt-dlp...")
                download_info = self._download_audio(resolved_url, audio_path)

                if not download_info.get('success'):
                    # Audio download/extraction failed. Common causes: ffprobe can't
                    # read the audio codec, the reel has no audio track, or the chosen
                    # format has no usable audio stream. Rather than hard-failing, fall
                    # back to vision-only extraction on the full video (frames don't
                    # need a usable audio stream). Only give up if the *video* can't be
                    # fetched either.
                    audio_error = download_info.get('error', 'Failed to download audio')
                    logger.warning(
                        f"Audio download failed ({audio_error[:160]}); "
                        f"falling back to vision-only extraction"
                    )
                    return self._vision_only_fallback(
                        platform=platform,
                        url=url,
                        resolved_url=resolved_url,
                        temp_dir=temp_dir,
                        tikwm_metadata=tikwm_metadata,
                        start_time=start_time,
                        audio_error=audio_error,
                    )

            # Add metadata to download_info for downstream methods
            download_info['platform'] = platform
            download_info['url'] = url

            # Step 2.5: Description-first analysis
            # Check if the video description already contains a full recipe
            video_title = download_info.get('title', '')
            video_description = download_info.get('description', video_title)

            if video_title or video_description:
                logger.info("Analyzing video description for recipe content...")
                desc_analysis = self._analyze_description(video_title, video_description, platform)

                # Early reject: not a recipe video
                if not desc_analysis.get('is_recipe', True) and desc_analysis.get('confidence', 0) >= 0.8:
                    processing_time = time.time() - start_time
                    logger.info(f"❌ Video rejected as non-recipe from description (confidence: {desc_analysis.get('confidence', 0):.2f}): {desc_analysis.get('rejection_reason', 'unknown')}")
                    return ParseResult(
                        success=False,
                        error_code="NOT_A_RECIPE",
                        error_message=f"This video doesn't appear to be a recipe: {desc_analysis.get('rejection_reason', 'No recipe content detected')}",
                        parser_name=self.parser_name,
                        extraction_method="description_rejected"
                    )

                # Full recipe found in description — skip audio/vision entirely
                if desc_analysis.get('has_full_recipe', False) and desc_analysis.get('confidence', 0) >= 0.8 and desc_analysis.get('recipe'):
                    processing_time = time.time() - start_time
                    logger.info(f"✅ Full recipe found in description! Skipping audio/vision pipeline (saved ~${self._estimate_cost('audio_only'):.3f}+)")

                    recipe_data = desc_analysis['recipe']
                    # Ensure recipe has a name
                    if not recipe_data.get('name'):
                        recipe_data['name'] = video_title.split('\n')[0][:100] if video_title else 'Untitled Recipe'

                    # Convert structured ingredients to strings for downstream processor
                    if recipe_data.get('ingredients'):
                        string_ingredients = []
                        for ing in recipe_data['ingredients']:
                            if isinstance(ing, dict):
                                parts = [ing.get('quantity', ''), ing.get('unit', ''), ing.get('name', '')]
                                string_ingredients.append(' '.join(p for p in parts if p).strip())
                            else:
                                string_ingredients.append(str(ing))
                        recipe_data['ingredients'] = string_ingredients

                    return ParseResult(
                        success=True,
                        data=recipe_data,
                        parser_name=self.parser_name,
                        confidence_score=desc_analysis.get('confidence', 0.8),
                        extraction_method="description_only",
                        frames_used=0,
                        estimated_cost=0.001,
                    )

                # Partial recipe or low confidence — continue with audio/vision pipeline
                if desc_analysis.get('is_recipe', True):
                    logger.info(f"Description suggests recipe but incomplete (confidence: {desc_analysis.get('confidence', 0):.2f}). Continuing with audio/vision pipeline.")

            # Step 3: Try audio extraction
            logger.info("Attempting audio-only extraction...")
            audio_result = await self._try_audio_extraction(audio_path, download_info)

            # Step 4: Calculate confidence if audio succeeded
            confidence = 0.0
            if audio_result['success']:
                confidence = self._calculate_audio_confidence(
                    transcript=audio_result.get('transcript', ''),
                    recipe_data=audio_result.get('recipe_data', {})
                )
                logger.info(f"Audio confidence: {confidence:.2f}")
            else:
                logger.info(f"Audio extraction failed: {audio_result.get('reason')}")
                confidence = audio_result.get('confidence', 0.0)

            # Get platform-specific configuration
            platform_config = self._get_platform_config(platform)
            audio_threshold = platform_config['audio_confidence_threshold']
            hybrid_threshold = platform_config['hybrid_confidence_threshold']
            default_frames = platform_config['default_frames']

            logger.info(f"Platform: {platform or 'unknown'} | Audio threshold: {audio_threshold}, Hybrid threshold: {hybrid_threshold}")

            # Step 5: Route based on confidence (or forced mode) with platform-specific thresholds
            extraction_method = None
            frames_used = 0
            final_recipe = None
            fallback_reason = None

            if force_mode == "audio" or (not force_mode and confidence >= audio_threshold):
                # HIGH CONFIDENCE - Use audio-only result
                extraction_method = "audio_only"
                frames_used = 0

                if audio_result['success']:
                    logger.info(f"✓ High confidence ({confidence:.2f}) - using audio-only (${self._estimate_cost('audio_only'):.3f})")
                    final_recipe = audio_result['recipe_data']
                else:
                    # Audio failed but we were trying audio-only - fallback to vision
                    logger.warning("Audio-only failed, falling back to vision-only")
                    fallback_reason = audio_result.get('reason')
                    extraction_method = "vision_only"
                    frames_used = platform_config['max_frames']

            elif force_mode == "hybrid" or (not force_mode and confidence >= hybrid_threshold):
                # MEDIUM CONFIDENCE - Hybrid mode (audio + platform-specific frames)
                extraction_method = "hybrid"
                frames_used = default_frames

                logger.info(f"~ Medium confidence ({confidence:.2f}) - using hybrid mode (${self._estimate_cost('hybrid', frames_used):.3f})")

                # Download video and extract frames
                video_path = self._download_video_for_platform(
                    platform, resolved_url, temp_dir, tikwm_metadata
                )
                frames = self._extract_key_frames(video_path, num_frames=frames_used)

                # TikTok-specific: Detect picture slideshows and force vision-only
                if platform == 'tiktok' and platform_config.get('detect_slideshows'):
                    is_slideshow = self._is_slideshow_video(frames)
                    if is_slideshow:
                        logger.info("🖼️  Detected TikTok picture slideshow - switching to vision-only mode")
                        extraction_method = "vision_only"
                        fallback_reason = "tiktok_slideshow_detected"
                        # Extract more frames for slideshows (each frame = different recipe step)
                        frames = self._extract_key_frames(video_path, num_frames=platform_config['max_frames'])
                        frames_used = len(frames)
                        # Vision-only for slideshows (audio is usually just background music)
                        final_recipe = self._vision_extract_recipe(
                            frames=frames,
                            audio_transcript=None,
                            video_metadata=download_info,
                            platform=platform
                        )
                    else:
                        # Normal hybrid mode
                        final_recipe = self._vision_extract_recipe(
                            frames=frames,
                            audio_transcript=audio_result.get('transcript'),
                            video_metadata=download_info,
                            platform=platform
                        )
                else:
                    # Use vision with audio transcript
                    final_recipe = self._vision_extract_recipe(
                        frames=frames,
                        audio_transcript=audio_result.get('transcript'),
                        video_metadata=download_info,
                        platform=platform
                    )

            else:
                # LOW CONFIDENCE - Vision-only mode (platform-specific frames, ignore audio)
                extraction_method = "vision_only"
                frames_used = platform_config['max_frames']

                logger.info(f"✗ Low confidence ({confidence:.2f}) - using vision-only (${self._estimate_cost('vision_only', frames_used):.3f})")
                fallback_reason = audio_result.get('reason') if not audio_result['success'] else "low_confidence"

                # Download video and extract frames
                video_path = self._download_video_for_platform(
                    platform, resolved_url, temp_dir, tikwm_metadata
                )
                frames = self._extract_key_frames(video_path, num_frames=frames_used)

                # Vision-only (ignore poor audio)
                final_recipe = self._vision_extract_recipe(
                    frames=frames,
                    audio_transcript=None,
                    video_metadata=download_info,
                    platform=platform
                )

            # Check if we got a recipe
            if not final_recipe:
                return ParseResult(
                    success=False,
                    error_code="RECIPE_EXTRACTION_FAILED",
                    error_message="Could not extract recipe from video",
                    parser_name=self.parser_name,
                    extraction_method=extraction_method,
                    frames_used=frames_used
                )

            # Calculate warnings
            warnings = self._generate_warnings(final_recipe)

            # Estimate cost (legacy simple estimate)
            estimated_cost = self._estimate_cost(
                extraction_method,
                frames_used=frames_used,
                transcript_length=len(audio_result.get('transcript', ''))
            )

            # Calculate detailed cost breakdown (Issue #39)
            transcript = audio_result.get('transcript', '')
            transcript_tokens = len(transcript) // 4 if transcript else 0  # Rough estimate: 4 chars/token

            # Get audio duration from download_info or estimate
            audio_duration = download_info.get('duration', 60.0)  # Default 60s if not available

            # Get video file size if we downloaded it
            video_size_mb = 0.0
            if temp_dir and os.path.exists(temp_dir):
                # Check if video was downloaded
                video_files = [f for f in os.listdir(temp_dir) if f.endswith(('.mp4', '.webm', '.mkv'))]
                if video_files:
                    video_path = os.path.join(temp_dir, video_files[0])
                    video_size_mb = os.path.getsize(video_path) / (1024 * 1024)  # Convert to MB

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Calculate detailed cost breakdown
            extraction_data = {
                'audio_duration_seconds': audio_duration,
                'transcript_tokens': transcript_tokens,
                'output_tokens': 500,  # Estimate GPT-4 output tokens
                'frames_used': frames_used,
                'video_size_mb': video_size_mb
            }
            cost_breakdown = self._calculate_extraction_cost(extraction_data)

            logger.info(f"✓ Successfully extracted recipe: {final_recipe.get('name', 'Unknown')} via {extraction_method}")
            logger.info(f"💰 Cost breakdown: ${cost_breakdown['total']:.4f} (whisper: ${cost_breakdown['whisper_transcription']:.4f}, gpt4_text: ${cost_breakdown['gpt4_text']:.4f}, gpt4_vision: ${cost_breakdown['gpt4_vision']:.4f})")

            return ParseResult(
                success=True,
                data=final_recipe,
                parser_name=self.parser_name,
                confidence_score=confidence,
                warnings=warnings,
                extraction_method=extraction_method,
                frames_used=frames_used,
                estimated_cost=estimated_cost,
                fallback_reason=fallback_reason,
                # Cost tracking fields (Issue #39)
                cost_breakdown=cost_breakdown,
                audio_duration_seconds=audio_duration,
                video_size_mb=video_size_mb,
                processing_time_ms=processing_time_ms,
                transcript_tokens=transcript_tokens,
                output_tokens=500  # Estimate
            )

        except Exception as e:
            logger.error(f"Error parsing video: {e}", exc_info=True)
            return ParseResult(
                success=False,
                error_code="PARSE_ERROR",
                error_message=str(e),
                parser_name=self.parser_name
            )
        finally:
            # Cleanup temp files
            if temp_dir and os.path.exists(temp_dir):
                import shutil
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp dir: {e}")

    def _vision_only_fallback(
        self,
        platform: str,
        url: str,
        resolved_url: str,
        temp_dir: str,
        tikwm_metadata: Optional[Dict[str, Any]],
        start_time: float,
        audio_error: str,
    ) -> ParseResult:
        """
        Vision-only extraction used when the audio pipeline can't run.

        Downloads the full video and extracts a recipe from key frames via
        GPT-4 Vision, with no audio transcript. This recovers reels where audio
        extraction fails (e.g. ffprobe "unable to obtain file audio codec",
        no audio track) but the visual content is still a usable recipe.

        Returns a successful ParseResult on success, or a failure ParseResult
        (DOWNLOAD_FAILED if the video itself can't be fetched, otherwise
        RECIPE_EXTRACTION_FAILED) so the caller can return it directly.
        """
        platform_config = self._get_platform_config(platform)
        frames_used = platform_config['max_frames']

        # Download the full video (frame extraction doesn't need a usable audio stream).
        try:
            video_path = self._download_video_for_platform(
                platform, resolved_url, temp_dir, tikwm_metadata
            )
        except Exception as e:
            logger.error(f"Vision fallback: video download failed: {e}")
            return ParseResult(
                success=False,
                error_code="DOWNLOAD_FAILED",
                # Surface the original audio error too; the video download is the
                # secondary failure that closed off the fallback.
                error_message=f"Audio extraction failed ({audio_error}); "
                              f"video fallback also failed: {e}",
                parser_name=self.parser_name,
            )

        frames = self._extract_key_frames(video_path, num_frames=frames_used)
        if not frames:
            return ParseResult(
                success=False,
                error_code="DOWNLOAD_FAILED",
                error_message=f"Audio extraction failed ({audio_error}); "
                              f"could not extract frames from video for vision fallback",
                parser_name=self.parser_name,
            )

        final_recipe = self._vision_extract_recipe(
            frames=frames,
            audio_transcript=None,
            video_metadata={'platform': platform, 'url': url},
            platform=platform,
        )

        if not final_recipe:
            return ParseResult(
                success=False,
                error_code="RECIPE_EXTRACTION_FAILED",
                error_message="Could not extract recipe from video (vision fallback)",
                parser_name=self.parser_name,
                extraction_method="vision_only",
                frames_used=len(frames),
            )

        warnings = self._generate_warnings(final_recipe)
        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"✓ Recovered recipe via vision-only fallback: "
            f"{final_recipe.get('name', 'Unknown')} ({len(frames)} frames)"
        )

        return ParseResult(
            success=True,
            data=final_recipe,
            parser_name=self.parser_name,
            confidence_score=0.0,  # No audio confidence; recipe came from frames.
            warnings=warnings,
            extraction_method="vision_only",
            frames_used=len(frames),
            estimated_cost=self._estimate_cost("vision_only", frames_used=len(frames)),
            fallback_reason="audio_download_failed",
            processing_time_ms=processing_time_ms,
            output_tokens=500,
        )

    def _fetch_tiktok_metadata_via_tikwm(self, url: str) -> Dict[str, Any]:
        """
        Fetch TikTok video metadata via TikWM API.

        Bypasses yt-dlp entirely for TikTok by using the TikWM service,
        which provides direct CDN URLs for video and audio downloads.

        Args:
            url: TikTok video URL

        Returns:
            Dict with keys:
                - success: bool
                - title: str (video title/caption)
                - description: str (same as title for TikTok)
                - video_url: str (direct CDN URL for video mp4)
                - audio_url: str (direct CDN URL for audio/music)
                - duration: int (video duration in seconds)
                - author: str (creator username)
                - video_id: str (TikTok video ID)
                - error: str (only if success=False)
        """
        api_url = f"https://www.tikwm.com/api/?url={url}"
        start_time = time.time()

        try:
            response = requests.get(api_url, timeout=5)
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.info(f"TikWM API response: status={response.status_code}, time={elapsed_ms}ms")

            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f"TikWM returned HTTP {response.status_code}"
                }

            result = response.json()

            # TikWM returns {"code": 0, "data": {...}} on success
            if result.get('code') != 0:
                error_msg = result.get('msg', 'Unknown TikWM error')
                logger.warning(f"TikWM API error: {error_msg}")
                return {
                    'success': False,
                    'error': f"TikWM error: {error_msg}"
                }

            data = result.get('data', {})
            if not data:
                return {
                    'success': False,
                    'error': 'TikWM returned empty data'
                }

            title = data.get('title', '')
            return {
                'success': True,
                'title': title,
                'description': title,  # TikTok captions serve as both
                'video_url': data.get('play', ''),
                'audio_url': data.get('music', ''),
                'duration': data.get('duration', 0),
                'author': data.get('author', {}).get('unique_id', ''),
                'video_id': str(data.get('id', '')),
            }

        except requests.Timeout:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"TikWM API timed out after {elapsed_ms}ms")
            return {
                'success': False,
                'error': 'TikWM API request timed out'
            }
        except requests.RequestException as e:
            logger.warning(f"TikWM API request failed: {e}")
            return {
                'success': False,
                'error': f"TikWM request failed: {str(e)}"
            }
        except (ValueError, KeyError) as e:
            logger.warning(f"TikWM API response parse error: {e}")
            return {
                'success': False,
                'error': f"TikWM response parse error: {str(e)}"
            }

    def _download_from_url(self, url: str, output_path: str) -> Dict[str, Any]:
        """
        Download a file from a direct URL (e.g., TikWM CDN link).

        Simple streaming download used for TikWM video/audio URLs.
        Not used for yt-dlp downloads.

        Args:
            url: Direct download URL
            output_path: Local file path to write to

        Returns:
            Dict with keys:
                - success: bool
                - error: str (only if success=False)
        """
        try:
            response = requests.get(url, stream=True, timeout=60)

            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f"Download returned HTTP {response.status_code}"
                }

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

            file_size = os.path.getsize(output_path)
            logger.info(f"Downloaded {file_size / 1024:.1f} KB to {output_path}")

            return {'success': True}

        except requests.Timeout:
            return {
                'success': False,
                'error': 'Download timed out after 60 seconds'
            }
        except requests.RequestException as e:
            return {
                'success': False,
                'error': f"Download failed: {str(e)}"
            }
        except IOError as e:
            return {
                'success': False,
                'error': f"Failed to write file: {str(e)}"
            }

    def _download_audio(self, url: str, output_path: str) -> Dict[str, Any]:
        """
        Download audio directly using yt-dlp's audio-only mode.
        
        This is faster and more efficient than downloading full video + ffmpeg extraction.
        Uses: yt-dlp -f bestaudio --extract-audio --audio-format mp3
        
        Returns dict with success, title, description, error
        """
        try:
            # First, get video info (title, description) - this is a lightweight metadata fetch
            info_cmd = self._ytdlp_base_args() + [
                '--dump-json',
                '--no-warnings',
                '--no-download',
                url
            ]

            info_result = subprocess.run(
                info_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            title = ""
            description = ""

            if info_result.returncode == 0:
                try:
                    info = json.loads(info_result.stdout)
                    title = info.get('title', '')
                    description = info.get('description', '')
                except json.JSONDecodeError:
                    logger.warning("Could not parse video info JSON")

            # Download audio only (much faster than full video)
            # Remove .mp3 extension as yt-dlp will add it
            output_template = output_path.replace('.mp3', '')

            download_cmd = self._ytdlp_base_args() + [
                '-f', 'bestaudio/best',
                '--extract-audio',
                '--audio-format', 'mp3',
                '--audio-quality', '64K',
                '-o', output_template + '.%(ext)s',
                '--no-warnings',
                '--no-playlist',
                '--postprocessor-args', 'ffmpeg:-ar 16000 -ac 1',
                url
            ]
            
            result = subprocess.run(
                download_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown yt-dlp error"
                logger.error(f"yt-dlp audio download failed: {error_msg}")
                return {'success': False, 'error': error_msg}
            
            # Check if file was downloaded (handle various extensions)
            if not os.path.exists(output_path):
                dir_path = os.path.dirname(output_path)
                base_name = os.path.basename(output_template)
                for f in os.listdir(dir_path):
                    if f.startswith(base_name) and f.endswith(('.mp3', '.m4a', '.opus', '.webm')):
                        actual_path = os.path.join(dir_path, f)
                        if actual_path != output_path:
                            os.rename(actual_path, output_path)
                        break
            
            if not os.path.exists(output_path):
                return {'success': False, 'error': 'Audio file not found after download'}
            
            file_size = os.path.getsize(output_path)
            logger.info(f"Downloaded audio: {file_size / 1024:.1f} KB (audio-only mode)")
            
            return {
                'success': True,
                'title': title,
                'description': description,
                'file_size': file_size
            }
            
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Audio download timed out'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _download_video_with_frames(self, url: str, video_path: str, audio_path: str) -> Dict[str, Any]:
        """
        Download full video when OCR/frame analysis is needed.
        
        This is the slower path - only use when visual content extraction is required.
        Returns dict with success, title, description, error
        """
        try:
            # Get video info
            info_cmd = self._ytdlp_base_args() + [
                '--dump-json',
                '--no-warnings',
                '--no-download',
                url
            ]

            info_result = subprocess.run(
                info_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )

            title = ""
            description = ""

            if info_result.returncode == 0:
                try:
                    info = json.loads(info_result.stdout)
                    title = info.get('title', '')
                    description = info.get('description', '')
                except json.JSONDecodeError:
                    logger.warning("Could not parse video info JSON")

            # Download full video
            download_cmd = self._ytdlp_base_args() + [
                '-f', 'best[ext=mp4]/best',
                '-o', video_path,
                '--no-warnings',
                '--no-playlist',
                url
            ]
            
            result = subprocess.run(
                download_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown yt-dlp error"
                logger.error(f"yt-dlp video download failed: {error_msg}")
                return {'success': False, 'error': error_msg}
            
            # Extract audio with ffmpeg
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',
                '-acodec', 'libmp3lame',
                '-ar', '16000',
                '-ac', '1',
                '-b:a', '64k',
                '-y',
                audio_path
            ]
            
            ffmpeg_result = subprocess.run(
                ffmpeg_cmd,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if ffmpeg_result.returncode != 0:
                return {'success': False, 'error': 'Failed to extract audio from video'}
            
            video_size = os.path.getsize(video_path) if os.path.exists(video_path) else 0
            audio_size = os.path.getsize(audio_path) if os.path.exists(audio_path) else 0
            
            logger.info(f"Downloaded video: {video_size / 1024 / 1024:.1f} MB, extracted audio: {audio_size / 1024:.1f} KB")
            
            return {
                'success': True,
                'title': title,
                'description': description,
                'video_path': video_path,
                'audio_path': audio_path
            }
            
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Video download timed out'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def _transcribe_audio(self, audio_path: str) -> Optional[str]:
        """
        Transcribe audio using OpenAI Whisper API.
        
        Returns transcript text or None on failure.
        """
        try:
            with open(audio_path, 'rb') as audio_file:
                response = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en",  # Optimize for English
                    response_format="text"
                )
            
            transcript = response.strip() if isinstance(response, str) else str(response).strip()
            
            if not transcript or len(transcript) < 10:
                logger.warning("Transcript too short or empty")
                return None
                
            return transcript
            
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return None

    def _parse_transcript_to_recipe(
        self, 
        transcript: str, 
        video_title: str,
        video_description: str,
        platform: str,
        url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Parse transcript with GPT-4 to extract structured recipe.
        
        Returns recipe dict or None if not a cooking video.
        """
        try:
            prompt = f"""You are a recipe extraction expert. Analyze this video transcript and extract a structured recipe.

VIDEO INFORMATION:
- Platform: {platform}
- Title: {video_title}
- Description: {video_description}

TRANSCRIPT:
{transcript}

INSTRUCTIONS:
1. If this is NOT a cooking/recipe video, respond with exactly: {{"is_recipe": false}}
2. If this IS a cooking video, extract the recipe into this JSON format:

{{
    "is_recipe": true,
    "name": "Recipe name (infer from context if not explicitly stated)",
    "description": "Brief description of the dish",
    "ingredients": [
        "List each ingredient with quantity and unit as spoken",
        "e.g., '2 cups flour', '1 tablespoon olive oil'"
    ],
    "steps": [
        "Step 1: Description of what to do",
        "Step 2: Next action",
        "..."
    ],
    "servings": null or number if mentioned,
    "prep_time_minutes": null or number if mentioned,
    "cook_time_minutes": null or number if mentioned,
    "total_time_minutes": null or number if mentioned,
    "tips": ["Any tips or variations mentioned"]
}}

IMPORTANT:
- Infer ingredients from actions if not explicitly listed (e.g., "add some butter" → "butter (amount not specified)")
- Capture cooking techniques and temperatures mentioned
- Keep the recipe name concise but descriptive
- If quantities are vague ("some", "a little"), note that in parentheses
- Only include actual cooking INGREDIENTS. Do NOT include:
  * Equipment or tools (fork, baking sheet, foil, skewer, frying pan, parchment paper)
  * Serving suggestions or garnishes that aren't prepared as part of the recipe (e.g., "serve with french fries" should NOT add "french fries" as an ingredient)
  * Non-food items (plastic wrap, kitchen twine, cheesecloth, paper towels)

Return ONLY valid JSON, no other text."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You extract structured recipes from video transcripts. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            # Clean up markdown code blocks if present
            if content.startswith('```'):
                content = re.sub(r'^```json?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
            
            parsed = json.loads(content)
            
            # Check if it's a recipe
            if not parsed.get('is_recipe', False):
                logger.info("GPT-4 determined this is not a cooking video")
                return None
            
            # Format into our standard recipe structure
            recipe_data = {
                "name": parsed.get('name', 'Video Recipe'),
                "description": parsed.get('description', ''),
                "ingredients": parsed.get('ingredients', []),
                "steps": parsed.get('steps', []),
                "servings": parsed.get('servings'),
                "prep_time_minutes": parsed.get('prep_time_minutes'),
                "cook_time_minutes": parsed.get('cook_time_minutes'),
                "total_time_minutes": parsed.get('total_time_minutes'),
                "image_url": None,  # Video thumbnail could be extracted later
                "video_url": url,
                "source_metadata": {
                    "author": None,  # Could be extracted from yt-dlp info
                    "site_name": platform.title(),
                    "host": platform,
                    "url": url,
                    "video_title": video_title,
                    "transcript": transcript[:1000] + "..." if len(transcript) > 1000 else transcript
                },
                "tips": parsed.get('tips', [])
            }
            
            return recipe_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT-4 response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"GPT-4 recipe extraction failed: {e}")
            return None

    def _analyze_description(
        self,
        title: str,
        description: str,
        platform: str
    ) -> Dict[str, Any]:
        """
        Analyze video title and description to determine if a full recipe is present.

        Uses GPT-4o-mini (cheaper text model) to classify the description and
        optionally extract a complete recipe if one is found in the text.

        This is a pre-processing step that can short-circuit expensive video
        download/transcription when the description already contains a full recipe,
        or quickly reject non-recipe content.

        Args:
            title: Video title
            description: Video description text
            platform: Platform name ('tiktok', 'instagram', 'youtube')

        Returns:
            Dict with keys:
                - is_recipe (bool): Whether this appears to be recipe content
                - has_full_recipe (bool): Whether description contains a COMPLETE recipe
                - confidence (float): 0.0-1.0 confidence score
                - recipe (dict or None): Extracted recipe if has_full_recipe is True
                - rejection_reason (str or None): Reason if is_recipe is False
        """
        error_result = {
            "is_recipe": False,
            "has_full_recipe": False,
            "confidence": 0.0,
            "recipe": None,
            "rejection_reason": "analysis_failed"
        }

        try:
            # Truncate description to avoid token waste
            truncated_description = description[:4000] if description else ""

            prompt = f"""You are a recipe content classifier. Analyze the following video title and description to determine if this is recipe content and whether a COMPLETE recipe is present in the text.

VIDEO INFORMATION:
- Platform: {platform}
- Title: {title or "(no title)"}
- Description: {truncated_description or "(no description)"}

CLASSIFICATION TASK:
1. Determine if this video appears to be about a recipe or cooking.
2. Determine if the description contains a COMPLETE recipe with BOTH:
   - Specific ingredient quantities (e.g., "2 cups flour", "1 tbsp oil")
   - Cooking steps/instructions (e.g., "Mix together", "Bake at 350F for 20 min")

EDGE CASES TO HANDLE:
- Hashtag-only descriptions (e.g., "#recipe #cooking #foodtok") → is_recipe may be true, but has_full_recipe is false
- "Link in bio" or "Full recipe on my website" → is_recipe true, has_full_recipe false
- Non-English descriptions → Analyze in the original language, still extract if possible
- Descriptions with only ingredient lists but no steps → has_full_recipe false
- Descriptions with only steps but no ingredients → has_full_recipe false
- Non-food content (dance, comedy, news, etc.) → is_recipe false

RESPONSE FORMAT (JSON):
{{
    "is_recipe": true/false,
    "has_full_recipe": true/false,
    "confidence": 0.0 to 1.0,
    "recipe": {{
        "name": "Recipe name",
        "description": "Brief description of the dish",
        "ingredients": [
            {{"quantity": "2", "unit": "cups", "name": "flour"}},
            {{"quantity": "1", "unit": "tbsp", "name": "olive oil"}}
        ],
        "steps": [
            "Step 1: Description",
            "Step 2: Description"
        ],
        "servings": null or number,
        "prep_time_minutes": null or number,
        "cook_time_minutes": null or number,
        "total_time_minutes": null or number,
        "cuisine": null or string,
        "difficulty": null or "easy"/"medium"/"hard",
        "tips": []
    }},
    "rejection_reason": null or "string explaining why this is not a recipe"
}}

RULES:
- Only include "recipe" when has_full_recipe is true. Set to null otherwise.
- confidence should reflect how certain you are about the is_recipe classification.
- For has_full_recipe, be strict: the description must have BOTH specific quantities AND steps.
- If the description is mostly hashtags or very short, confidence should be lower.
- Only include actual cooking INGREDIENTS. Do NOT include:
  * Equipment or tools (fork, baking sheet, foil, skewer, frying pan, parchment paper)
  * Serving suggestions or garnishes that aren't prepared as part of the recipe (e.g., "serve with french fries" should NOT add "french fries" as an ingredient)
  * Non-food items (plastic wrap, kitchen twine, cheesecloth, paper towels)
- Return ONLY valid JSON."""

            response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You classify video descriptions to detect recipe content. Return only valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.2,
                max_tokens=2000,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content.strip()

            # Clean up markdown code blocks if present
            if content.startswith('```'):
                content = re.sub(r'^```json?\s*', '', content)
                content = re.sub(r'\s*```$', '', content)

            result = json.loads(content)

            # Validate required fields with defaults
            result.setdefault("is_recipe", False)
            result.setdefault("has_full_recipe", False)
            result.setdefault("confidence", 0.0)
            result.setdefault("recipe", None)
            result.setdefault("rejection_reason", None)

            # Ensure confidence is a float in range
            try:
                result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
            except (TypeError, ValueError):
                result["confidence"] = 0.0

            # If not a recipe, clear recipe data
            if not result["is_recipe"]:
                result["recipe"] = None
                result["has_full_recipe"] = False

            # If no full recipe, clear recipe data
            if not result["has_full_recipe"]:
                result["recipe"] = None

            logger.info(
                f"Description analysis: is_recipe={result['is_recipe']}, "
                f"has_full_recipe={result['has_full_recipe']}, "
                f"confidence={result['confidence']:.2f}"
            )

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse description analysis response as JSON: {e}")
            return error_result
        except Exception as e:
            logger.error(f"Description analysis failed: {e}")
            return error_result

    def _generate_warnings(self, recipe_data: Dict[str, Any]) -> List[str]:
        """Generate warnings for missing or incomplete data."""
        warnings = []
        
        if not recipe_data.get('name'):
            warnings.append("Recipe name could not be determined")
        
        ingredients = recipe_data.get('ingredients', [])
        if not ingredients:
            warnings.append("No ingredients could be extracted")
        elif len(ingredients) < 3:
            warnings.append("Very few ingredients extracted - video may have incomplete information")
        
        # Check for vague quantities
        vague_count = sum(1 for i in ingredients if 'not specified' in str(i).lower() or 'some' in str(i).lower())
        if vague_count > 0:
            warnings.append(f"{vague_count} ingredient(s) have vague or unspecified quantities")
        
        steps = recipe_data.get('steps', [])
        if not steps:
            warnings.append("No cooking steps could be extracted")
        elif len(steps) < 2:
            warnings.append("Very few steps extracted - recipe may be incomplete")
        
        if not recipe_data.get('servings'):
            warnings.append("Servings not specified")
        
        if not recipe_data.get('total_time_minutes') and not recipe_data.get('cook_time_minutes'):
            warnings.append("Cooking time not specified")
        
        return warnings

    def _calculate_confidence(self, recipe_data: Dict[str, Any]) -> float:
        """
        Calculate confidence score based on data completeness.
        
        Returns score between 0.0 and 1.0
        """
        score = 0.0
        
        # Name: 15 points
        if recipe_data.get('name'):
            score += 0.15
        
        # Description: 5 points
        if recipe_data.get('description'):
            score += 0.05
        
        # Ingredients: up to 30 points
        ingredients = recipe_data.get('ingredients', [])
        if ingredients:
            ingredient_score = min(len(ingredients) / 10, 1.0) * 0.30
            score += ingredient_score
        
        # Steps: up to 30 points
        steps = recipe_data.get('steps', [])
        if steps:
            step_score = min(len(steps) / 6, 1.0) * 0.30
            score += step_score
        
        # Servings: 5 points
        if recipe_data.get('servings'):
            score += 0.05
        
        # Times: 10 points
        if recipe_data.get('total_time_minutes') or recipe_data.get('cook_time_minutes'):
            score += 0.10
        
        # Source URL: 5 points
        if recipe_data.get('video_url'):
            score += 0.05

        return min(score, 1.0)

    def _extract_key_frames(
        self,
        video_path: str,
        num_frames: int = 5,
        skip_similar: bool = True
    ) -> List[str]:
        """
        Extract key frames from video for GPT-4 Vision analysis.

        Uses ffmpeg to extract evenly-spaced frames, optimized for GPT-4 Vision API:
        - Frames scaled to max 1024px width (token optimization)
        - JPEG compression at 85% quality
        - Skip first/last 5% of video (intro/outro)
        - Optional similarity detection to avoid duplicate frames

        Args:
            video_path: Path to downloaded video file
            num_frames: Number of frames to extract (default: 5)
            skip_similar: Skip nearly identical frames (default: True)

        Returns:
            List of base64-encoded JPEG images ready for GPT-4 Vision API

        Raises:
            FileNotFoundError: If video file doesn't exist
            subprocess.CalledProcessError: If ffmpeg extraction fails
        """
        import base64
        from PIL import Image
        import hashlib

        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        logger.info(f"Extracting {num_frames} key frames from video...")

        # Create temp directory for frames
        temp_frame_dir = tempfile.mkdtemp(prefix="video_frames_")

        try:
            # Step 1: Get video duration
            duration = self._get_video_duration(video_path)
            if not duration:
                logger.warning("Could not determine video duration, using default extraction")
                duration = 60  # Assume 60 seconds

            # Skip first/last 5% of video
            start_time = duration * 0.05
            end_time = duration * 0.95
            effective_duration = end_time - start_time

            # Calculate frame interval
            if effective_duration <= 0 or num_frames <= 0:
                logger.warning(f"Invalid duration ({duration}s) or frame count ({num_frames})")
                return []

            frame_interval = effective_duration / (num_frames + 1)

            # Step 2: Extract frames at calculated intervals
            extracted_frames = []

            for i in range(1, num_frames + 1):
                timestamp = start_time + (i * frame_interval)
                frame_path = os.path.join(temp_frame_dir, f"frame_{i:03d}.jpg")

                # Extract single frame at timestamp with ffmpeg
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-ss', str(timestamp),  # Seek to timestamp
                    '-i', video_path,
                    '-vframes', '1',  # Extract 1 frame
                    '-vf', 'scale=1024:-1',  # Scale to 1024px width, maintain aspect
                    '-q:v', '2',  # JPEG quality (2 = ~85-90%)
                    '-y',  # Overwrite
                    frame_path
                ]

                result = subprocess.run(
                    ffmpeg_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                if result.returncode == 0 and os.path.exists(frame_path):
                    extracted_frames.append(frame_path)
                else:
                    logger.warning(f"Failed to extract frame at {timestamp:.2f}s")

            if not extracted_frames:
                logger.error("No frames could be extracted")
                return []

            logger.info(f"Extracted {len(extracted_frames)} frames successfully")

            # Step 3: Optional similarity filtering
            if skip_similar and len(extracted_frames) > 1:
                filtered_frames = self._filter_similar_frames(extracted_frames)
                logger.info(f"After similarity filtering: {len(filtered_frames)} frames")
            else:
                filtered_frames = extracted_frames

            # Step 4: Convert frames to base64
            base64_frames = []
            for frame_path in filtered_frames:
                try:
                    with Image.open(frame_path) as img:
                        # Convert to RGB if needed (some videos have RGBA)
                        if img.mode != 'RGB':
                            img = img.convert('RGB')

                        # Save to bytes buffer
                        import io
                        buffer = io.BytesIO()
                        img.save(buffer, format='JPEG', quality=85)
                        buffer.seek(0)

                        # Encode to base64
                        b64_string = base64.b64encode(buffer.read()).decode('utf-8')
                        base64_frames.append(b64_string)

                except Exception as e:
                    logger.warning(f"Failed to encode frame {frame_path}: {e}")

            logger.info(f"Encoded {len(base64_frames)} frames to base64")
            return base64_frames

        finally:
            # Cleanup temp directory
            import shutil
            try:
                shutil.rmtree(temp_frame_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp frames: {e}")

    def _get_video_duration(self, video_path: str) -> Optional[float]:
        """
        Get video duration in seconds using ffmpeg.

        Args:
            video_path: Path to video file

        Returns:
            Duration in seconds or None if could not determine
        """
        try:
            ffprobe_cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                video_path
            ]

            result = subprocess.run(
                ffprobe_cmd,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                duration = float(result.stdout.strip())
                logger.debug(f"Video duration: {duration:.2f}s")
                return duration

        except (ValueError, subprocess.SubprocessError) as e:
            logger.warning(f"Could not determine video duration: {e}")

        return None

    def _filter_similar_frames(self, frame_paths: List[str], similarity_threshold: float = 0.9) -> List[str]:
        """
        Filter out nearly identical consecutive frames.

        Uses perceptual hashing to detect similar frames (useful for slideshows).

        Args:
            frame_paths: List of frame file paths
            similarity_threshold: Frames with >threshold similarity are considered duplicates (0-1)

        Returns:
            Filtered list of frame paths with duplicates removed
        """
        from PIL import Image
        import hashlib

        if len(frame_paths) <= 1:
            return frame_paths

        filtered = [frame_paths[0]]  # Always keep first frame
        prev_hash = self._compute_frame_hash(frame_paths[0])

        for frame_path in frame_paths[1:]:
            curr_hash = self._compute_frame_hash(frame_path)

            # Compare hashes (simple approach: exact match = duplicate)
            # For more sophisticated similarity, could use hamming distance
            if curr_hash != prev_hash:
                filtered.append(frame_path)
                prev_hash = curr_hash
            else:
                logger.debug(f"Skipping similar frame: {frame_path}")

        return filtered

    def _compute_frame_hash(self, frame_path: str) -> str:
        """
        Compute perceptual hash of frame image.

        Uses difference hash (dHash) algorithm which is more robust for detecting
        actual image differences compared to simple average hash.

        Args:
            frame_path: Path to frame image

        Returns:
            Hash string
        """
        from PIL import Image
        import hashlib

        try:
            with Image.open(frame_path) as img:
                # Resize to 9x8 for dHash (need 9 to compute 8 differences)
                img = img.resize((9, 8)).convert('L')

                # Get pixel data
                pixels = list(img.getdata())

                # Compute difference hash (dHash)
                # Compare each pixel to its neighbor to the right
                bits = ''
                for row in range(8):
                    for col in range(8):
                        pixel_index = row * 9 + col
                        left_pixel = pixels[pixel_index]
                        right_pixel = pixels[pixel_index + 1]
                        # Set bit if left pixel is brighter than right
                        bits += '1' if left_pixel > right_pixel else '0'

                # Convert to hex hash
                return hashlib.md5(bits.encode()).hexdigest()

        except Exception as e:
            logger.warning(f"Failed to compute frame hash: {e}")
            return ""

    def _vision_extract_recipe(
        self,
        frames: List[str],
        audio_transcript: Optional[str] = None,
        video_metadata: Optional[Dict] = None,
        platform: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Extract recipe from video frames using GPT-4 Vision API.

        Analyzes frames to extract structured recipe data from:
        - Picture slideshow TikToks with text overlays
        - Silent cooking videos with visual instructions
        - Hybrid videos (combines visual + audio transcript)

        Args:
            frames: List of base64-encoded JPEG frame images
            audio_transcript: Optional audio transcript for hybrid mode
            video_metadata: Optional dict with 'title', 'description', 'platform'
            platform: Optional platform name for optimized prompts

        Returns:
            Recipe dict with standard structure, or None if not a recipe video

        Raises:
            Exception: If GPT-4 Vision API call fails after retries
        """
        if not frames:
            logger.warning("No frames provided for vision extraction")
            return None

        metadata = video_metadata or {}
        detected_platform = platform or metadata.get('platform', 'unknown')
        title = metadata.get('title', '')
        description = metadata.get('description', '')

        logger.info(f"Extracting recipe from {len(frames)} frames using GPT-4 Vision (platform: {detected_platform})...")

        # Build the prompt with platform-specific hints
        prompt = self._build_vision_prompt(
            platform=detected_platform,
            title=title,
            description=description,
            audio_transcript=audio_transcript
        )

        # Construct GPT-4 Vision API message
        message_content = [
            {
                "type": "text",
                "text": prompt
            }
        ]

        # Add frames as images
        for i, frame_b64 in enumerate(frames):
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{frame_b64}",
                    "detail": "high"  # High detail for better OCR
                }
            })

        messages = [
            {
                "role": "system",
                "content": "You are a recipe extraction expert. Analyze video frames to extract structured recipes from cooking videos. Read text overlays, identify ingredients visually, and return valid JSON."
            },
            {
                "role": "user",
                "content": message_content
            }
        ]

        # Call GPT-4 Vision API with retry logic
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=2000,
                    temperature=0.3
                )

                content = response.choices[0].message.content.strip()

                # Clean up markdown code blocks if present
                if content.startswith('```'):
                    content = re.sub(r'^```json?\s*', '', content)
                    content = re.sub(r'\s*```$', '', content)

                # Parse JSON response
                parsed = json.loads(content)

                # Check if it's a recipe
                if not parsed.get('is_recipe', False):
                    logger.info("GPT-4 Vision determined this is not a cooking video")
                    return None

                # Format into standard recipe structure
                recipe_data = {
                    "name": parsed.get('name', 'Video Recipe'),
                    "description": parsed.get('description', ''),
                    "ingredients": parsed.get('ingredients', []),
                    "steps": parsed.get('steps', []),
                    "servings": parsed.get('servings'),
                    "prep_time_minutes": parsed.get('prep_time_minutes'),
                    "cook_time_minutes": parsed.get('cook_time_minutes'),
                    "total_time_minutes": parsed.get('total_time_minutes'),
                    "image_url": None,
                    "video_url": metadata.get('url'),
                    "source_metadata": {
                        "author": None,
                        "site_name": platform.title(),
                        "host": platform,
                        "url": metadata.get('url'),
                        "video_title": title,
                        "extraction_method": "vision",
                        "frames_analyzed": len(frames),
                        "audio_available": audio_transcript is not None
                    },
                    "tips": parsed.get('tips', [])
                }

                logger.info(f"Successfully extracted recipe via vision: {recipe_data['name']}")
                return recipe_data

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse GPT-4 Vision response as JSON: {e}")
                logger.debug(f"Response content: {content[:500]}")

                if attempt < max_retries - 1:
                    logger.info(f"Retrying vision extraction (attempt {attempt + 2}/{max_retries})...")
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    return None

            except Exception as e:
                logger.error(f"GPT-4 Vision API call failed: {e}")

                if attempt < max_retries - 1:
                    logger.info(f"Retrying vision extraction (attempt {attempt + 2}/{max_retries})...")
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(f"All retries exhausted for GPT-4 Vision API")
                    return None

        return None

    def _build_vision_prompt(
        self,
        platform: str,
        title: str,
        description: str,
        audio_transcript: Optional[str] = None
    ) -> str:
        """
        Build optimized prompt for GPT-4 Vision recipe extraction.

        Tailors prompt based on platform and whether audio is available.

        Args:
            platform: Video platform (tiktok, instagram, youtube)
            title: Video title
            description: Video description
            audio_transcript: Optional audio transcript

        Returns:
            Formatted prompt string
        """
        base_prompt = f"""You are analyzing frames from a short-form cooking video to extract a recipe.

VIDEO INFORMATION:
- Platform: {platform}
- Title: {title or "Not provided"}
- Description: {description or "Not provided"}
- Audio Transcript: {audio_transcript or "No audio available (silent video or poor quality)"}

YOUR TASKS:
1. Examine all frames carefully and read any text overlays (ingredients, measurements, steps)
2. Identify ingredients visible in the video
3. Note cooking steps shown visually or written as text
4. If this is NOT a cooking/recipe video, respond with exactly: {{"is_recipe": false}}
5. If this IS a cooking video, extract the recipe into this JSON format:

{{
    "is_recipe": true,
    "name": "Recipe name (read from video or infer from context)",
    "description": "Brief description of the dish",
    "ingredients": [
        "List ingredients with quantities from text overlays or visual context",
        "e.g., '2 cups flour', '1 tablespoon olive oil', '3 cloves garlic'"
    ],
    "steps": [
        "Step 1: Description from visual/text",
        "Step 2: Next action",
        "..."
    ],
    "servings": null or number if mentioned,
    "prep_time_minutes": null or number if mentioned,
    "cook_time_minutes": null or number if mentioned,
    "total_time_minutes": null or number if mentioned,
    "tips": ["Any tips or variations shown/mentioned"]
}}

IMPORTANT INSTRUCTIONS:
- **Read text overlays carefully** - ingredients are often listed as on-screen text
- **Infer from visual context** - if you see butter being added but quantity isn't shown, note "butter (amount not specified)"
- **Combine audio + visual** - if audio transcript is available, use it to supplement what you see
- **Handle abbreviations** - tbsp = tablespoon, tsp = teaspoon, c = cup
- **Preserve measurements** - keep exact quantities as shown (don't convert units)
- **Sequential steps** - list steps in the order shown in the video
- **Only include actual cooking INGREDIENTS** - Do NOT include:
  * Equipment or tools (fork, baking sheet, foil, skewer, frying pan, parchment paper)
  * Serving suggestions or garnishes that aren't prepared as part of the recipe (e.g., "serve with french fries" should NOT add "french fries" as an ingredient)
  * Non-food items (plastic wrap, kitchen twine, cheesecloth, paper towels)
"""

        # Add platform-specific hints
        if platform == 'tiktok':
            base_prompt += """
TIKTOK-SPECIFIC NOTES:
- Pay close attention to text overlays - TikTok recipes often use on-screen text for ingredients
- Text may be abbreviated or stylized (e.g., "2c flour" = "2 cups flour")
- Steps are sometimes numbered visually (1., 2., 3.)
- This may be a picture slideshow - read all text in each frame
"""
        elif platform == 'instagram':
            base_prompt += """
INSTAGRAM-SPECIFIC NOTES:
- Look for captions/subtitles at bottom of frames
- Ingredients may be shown aesthetically without speaking them
- Pay attention to visual presentation for plating/serving suggestions
"""
        elif platform == 'youtube':
            base_prompt += """
YOUTUBE-SPECIFIC NOTES:
- Professional content - may have clear text overlays or graphics
- Look for on-screen graphics showing ingredients and measurements
"""

        base_prompt += """
Return ONLY valid JSON, no other text or explanation."""

        return base_prompt

    def _calculate_audio_confidence(
        self,
        transcript: str,
        recipe_data: Dict[str, Any],
        audio_metadata: Optional[Dict] = None
    ) -> float:
        """
        Calculate confidence score for audio-based recipe extraction.

        Analyzes multiple factors to determine if audio extraction is reliable
        or if vision-based fallback is needed for better quality.

        Args:
            transcript: Whisper transcription text
            recipe_data: Extracted recipe from GPT-4 (audio-only)
            audio_metadata: Optional audio analysis (volume, clarity, duration)

        Returns:
            Confidence score 0.0-1.0 where:
            - >= 0.7: High confidence (use audio-only)
            - 0.4-0.7: Medium confidence (use hybrid audio+vision)
            - < 0.4: Low confidence (use vision-only)

        Scoring Factors:
            - Transcript Quality (30%): length, coherence, clarity
            - Recipe Completeness (40%): name, ingredients, steps, quantities
            - Cooking Content (20%): cooking vocabulary, measurements
            - GPT-4 Confidence (10%): metadata completeness
        """
        if not transcript or not recipe_data:
            logger.warning("Empty transcript or recipe data for confidence calculation")
            return 0.0

        score = 0.0

        # 1. TRANSCRIPT QUALITY (30% weight)
        transcript_lower = transcript.lower()
        word_count = len(transcript.split())

        # Length scoring (25% of total)
        if word_count >= 100:
            score += 0.25
        elif word_count >= 50:
            score += 0.15
        elif word_count >= 20:
            score += 0.08
        else:
            score += 0.02

        # Clarity scoring (5% of total)
        inaudible_markers = transcript.count('[inaudible]') + transcript.count('[music]')
        if word_count > 0:
            clarity_ratio = 1.0 - min(inaudible_markers / word_count, 1.0)
            score += clarity_ratio * 0.05

        # 2. RECIPE COMPLETENESS (40% weight)

        # Has recipe name (10%)
        if recipe_data.get('name') and len(recipe_data['name']) > 3:
            score += 0.10

        # Has adequate ingredients (15%)
        ingredients = recipe_data.get('ingredients', [])
        if len(ingredients) >= 5:
            score += 0.15
        elif len(ingredients) >= 3:
            score += 0.10
        elif len(ingredients) >= 1:
            score += 0.05

        # Has cooking steps (15%)
        steps = recipe_data.get('steps', [])
        if len(steps) >= 3:
            score += 0.15
        elif len(steps) >= 2:
            score += 0.10
        elif len(steps) >= 1:
            score += 0.05

        # Has quantities in ingredients (bonus within 40%)
        if ingredients:
            has_quantities = sum(
                1 for ing in ingredients
                if any(unit in str(ing).lower() for unit in ['cup', 'tablespoon', 'teaspoon', 'tbsp', 'tsp', 'gram', 'oz', 'lb', 'ml', 'liter'])
            )
            quantity_ratio = has_quantities / len(ingredients)
            # This is already counted in the 15% for ingredients, so it's a quality boost
            if quantity_ratio >= 0.5:
                score += 0.05

        # 3. COOKING CONTENT DETECTION (20% weight)

        # Cooking action verbs (10%)
        cooking_verbs = [
            'add', 'mix', 'stir', 'cook', 'bake', 'fry', 'boil', 'simmer',
            'chop', 'dice', 'slice', 'season', 'heat', 'preheat', 'combine',
            'whisk', 'blend', 'pour', 'serve', 'prepare', 'marinate', 'grill'
        ]
        verb_count = sum(1 for verb in cooking_verbs if verb in transcript_lower)
        if verb_count >= 5:
            score += 0.10
        elif verb_count >= 3:
            score += 0.07
        elif verb_count >= 1:
            score += 0.03

        # Measurement units present (5%)
        measurement_units = [
            'cup', 'cups', 'tablespoon', 'tablespoons', 'tbsp', 'teaspoon', 'teaspoons', 'tsp',
            'gram', 'grams', 'ounce', 'ounces', 'oz', 'pound', 'pounds', 'lb',
            'milliliter', 'ml', 'liter', 'pinch', 'dash'
        ]
        unit_count = sum(1 for unit in measurement_units if unit in transcript_lower)
        if unit_count >= 3:
            score += 0.05
        elif unit_count >= 1:
            score += 0.03

        # Negative signals - promotional content (reduces score)
        promotional_phrases = [
            'like and subscribe', 'follow me', 'check my bio', 'link in bio',
            'swipe up', 'check description', 'comment below', 'hit the bell'
        ]
        promo_count = sum(1 for phrase in promotional_phrases if phrase in transcript_lower)
        if promo_count > 0:
            score -= min(promo_count * 0.05, 0.15)  # Max penalty 0.15

        # 4. GPT-4 PARSER CONFIDENCE SIGNALS (10% weight)

        # Has metadata (servings, time) (5%)
        if recipe_data.get('servings') or recipe_data.get('total_time_minutes') or \
           recipe_data.get('prep_time_minutes') or recipe_data.get('cook_time_minutes'):
            score += 0.05

        # Detailed steps (average step length > 10 words) (5%)
        if steps:
            avg_step_length = sum(len(step.split()) for step in steps) / len(steps)
            if avg_step_length >= 15:
                score += 0.05
            elif avg_step_length >= 10:
                score += 0.03

        # Ensure score is in valid range [0.0, 1.0]
        final_score = max(0.0, min(score, 1.0))

        logger.info(f"Audio confidence score: {final_score:.2f} (words: {word_count}, ingredients: {len(ingredients)}, steps: {len(steps)})")

        return final_score

    async def _try_audio_extraction(
        self,
        audio_path: str,
        download_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Attempt audio-only recipe extraction with graceful degradation.

        Returns dict with:
            - success: bool
            - transcript: str (if successful)
            - recipe_data: dict (if successful)
            - confidence: float
            - reason: str (if failed)
        """
        try:
            # Transcribe audio
            transcript = self._transcribe_audio(audio_path)

            if not transcript or len(transcript) < 20:
                logger.warning("Insufficient audio content for extraction")
                return {
                    'success': False,
                    'confidence': 0.0,
                    'reason': 'insufficient_audio',
                    'transcript': transcript or ''
                }

            logger.info(f"Transcript ({len(transcript)} chars): {transcript[:200]}...")

            # Parse transcript to recipe
            recipe_data = self._parse_transcript_to_recipe(
                transcript=transcript,
                video_title=download_info.get('title', ''),
                video_description=download_info.get('description', ''),
                platform=download_info.get('platform', ''),
                url=download_info.get('url', '')
            )

            if not recipe_data:
                logger.warning("Could not extract recipe from transcript")
                return {
                    'success': False,
                    'confidence': 0.2,
                    'reason': 'not_a_recipe',
                    'transcript': transcript
                }

            # Check if GPT-4 determined it's not a recipe
            if not recipe_data.get('is_recipe', True):
                logger.info("GPT-4 determined this is not a cooking video")
                return {
                    'success': False,
                    'confidence': 0.1,
                    'reason': 'not_a_recipe',
                    'transcript': transcript
                }

            return {
                'success': True,
                'transcript': transcript,
                'recipe_data': recipe_data,
                'confidence': 1.0  # Will be recalculated by _calculate_audio_confidence
            }

        except Exception as e:
            logger.warning(f"Audio extraction failed: {e}")
            return {
                'success': False,
                'confidence': 0.0,
                'reason': str(e),
                'transcript': ''
            }

    def _get_optimal_frame_count(
        self,
        confidence: float,
        video_duration: Optional[int] = None
    ) -> int:
        """
        Determine optimal frame count based on confidence and video duration.

        Args:
            confidence: Audio confidence score (0.0-1.0)
            video_duration: Video duration in seconds (optional)

        Returns:
            Optimal number of frames to extract (1-10)
        """
        # Hybrid mode (medium confidence) - minimal frames
        if confidence >= 0.4:
            return 3

        # Low confidence - need more frames
        if video_duration and video_duration < 30:
            # Short video - fewer frames sufficient
            return 3
        else:
            # Longer video or unknown duration - more frames
            return 5

    def _download_video_for_platform(
        self,
        platform: str,
        url: str,
        temp_dir: str,
        tikwm_metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Download video file using the appropriate method for each platform.

        TikTok uses TikWM CDN URLs; Instagram/YouTube use yt-dlp.

        Args:
            platform: Detected platform name
            url: Original video URL
            temp_dir: Temporary directory for download
            tikwm_metadata: TikWM metadata dict (required for TikTok)

        Returns:
            Path to downloaded video file

        Raises:
            RuntimeError: If download fails
        """
        if platform == 'tiktok' and tikwm_metadata:
            video_url = tikwm_metadata.get('video_url', '')
            if not video_url:
                raise RuntimeError("TikWM did not return a video URL")

            video_path = os.path.join(temp_dir, "video.mp4")
            logger.info("Downloading TikTok video from TikWM CDN...")
            result = self._download_from_url(video_url, video_path)

            if not result.get('success'):
                raise RuntimeError(f"TikTok video download failed: {result.get('error', 'Unknown error')}")

            return video_path

        # Instagram/YouTube: use yt-dlp
        return self._download_video(url, temp_dir)

    def _download_video(self, url: str, temp_dir: str) -> str:
        """
        Download full video file for frame extraction.

        Args:
            url: Video URL
            temp_dir: Temporary directory for download

        Returns:
            Path to downloaded video file

        Raises:
            RuntimeError: If download fails
        """
        video_path = os.path.join(temp_dir, "video.mp4")

        try:
            cmd = self._ytdlp_base_args() + [
                '-f', 'best',  # Best quality video
                '-o', video_path,
                '--no-warnings',
                '--no-playlist',
                url
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown yt-dlp error"
                logger.error(f"Video download failed: {error_msg}")
                raise RuntimeError(f"Video download failed: {error_msg}")

            if not os.path.exists(video_path):
                raise RuntimeError(f"Video file not created: {video_path}")

            logger.info(f"Downloaded video: {video_path} ({os.path.getsize(video_path)} bytes)")
            return video_path

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Video download timed out after {self.timeout} seconds")
        except Exception as e:
            raise RuntimeError(f"Video download error: {str(e)}")

    def _estimate_cost(
        self,
        extraction_method: str,
        frames_used: int = 0,
        transcript_length: int = 0
    ) -> float:
        """
        Estimate API cost for the extraction.

        Costs (approximate):
        - Whisper API: $0.006 per minute (assume 1 min avg)
        - GPT-4: $0.01 per 1K tokens (assume 500 tokens)
        - GPT-4 Vision: $0.01 per image in high detail mode

        Args:
            extraction_method: "audio_only", "hybrid", or "vision_only"
            frames_used: Number of frames analyzed
            transcript_length: Length of transcript in chars

        Returns:
            Estimated cost in USD
        """
        # Whisper cost (always used for audio methods)
        whisper_cost = 0.006  # $0.006 per minute (assume 1 min average)

        # GPT-4 text cost (transcript parsing)
        gpt4_text_cost = 0.005  # ~500 tokens for parsing

        # GPT-4 Vision cost per frame (high detail mode)
        gpt4_vision_cost_per_frame = 0.01

        if extraction_method == "audio_only":
            return whisper_cost + gpt4_text_cost  # ~$0.011

        elif extraction_method == "hybrid":
            return whisper_cost + gpt4_text_cost + (frames_used * gpt4_vision_cost_per_frame)
            # With 3 frames: ~$0.041

        elif extraction_method == "vision_only":
            # May or may not use Whisper, but vision is primary cost
            return (frames_used * gpt4_vision_cost_per_frame)
            # With 5 frames: ~$0.05

        return 0.0

    def _calculate_extraction_cost(
        self,
        extraction_data: Dict[str, Any]
    ) -> Dict[str, float]:
        """
        Calculate detailed API costs for this extraction.

        Actual OpenAI pricing (as of 2025):
        - Whisper: $0.006 per minute
        - GPT-4o input: $2.50 per 1M tokens
        - GPT-4o output: $10.00 per 1M tokens
        - GPT-4 Vision: varies by image size and detail level
          - High detail (1024px): ~$0.03 per image

        Args:
            extraction_data: Dict with extraction metadata
                - audio_duration_seconds: Audio duration
                - transcript_tokens: Estimated input tokens for transcript
                - output_tokens: Estimated output tokens from GPT-4
                - frames_used: Number of frames analyzed
                - video_size_mb: Video file size

        Returns:
            Dict with cost breakdown: {
                "whisper_transcription": float,
                "gpt4_text": float,
                "gpt4_vision": float,
                "video_download": float,
                "total": float
            }
        """
        costs = {
            "whisper_transcription": 0.0,
            "gpt4_text": 0.0,
            "gpt4_vision": 0.0,
            "video_download": 0.0,
            "total": 0.0
        }

        # Whisper cost: $0.006 per minute
        if extraction_data.get('audio_duration_seconds'):
            audio_minutes = extraction_data['audio_duration_seconds'] / 60
            costs['whisper_transcription'] = audio_minutes * 0.006

        # GPT-4o text cost (for transcript parsing or vision analysis)
        input_tokens = extraction_data.get('transcript_tokens', 0)
        output_tokens = extraction_data.get('output_tokens', 500)  # Estimate 500 tokens

        if input_tokens > 0:
            # $2.50 per 1M input tokens, $10 per 1M output tokens
            input_cost = (input_tokens / 1_000_000) * 2.50
            output_cost = (output_tokens / 1_000_000) * 10.00
            costs['gpt4_text'] = input_cost + output_cost

        # GPT-4 Vision cost: ~$0.03 per high-detail image
        # (1024px width images use high-detail mode)
        if extraction_data.get('frames_used'):
            costs['gpt4_vision'] = extraction_data['frames_used'] * 0.03

        # Bandwidth cost (negligible, but included for completeness)
        # Estimate $0.0001 per MB
        if extraction_data.get('video_size_mb'):
            costs['video_download'] = extraction_data['video_size_mb'] * 0.0001

        # Calculate total
        costs['total'] = sum(v for k, v in costs.items() if k != 'total')

        return costs
