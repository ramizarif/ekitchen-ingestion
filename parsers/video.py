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
        
    @property
    def openai_client(self):
        """Lazy load OpenAI client."""
        if self._openai_client is None:
            from openai import OpenAI
            self._openai_client = OpenAI()
        return self._openai_client

    async def validate_url(self, url: str) -> bool:
        """Check if URL is a supported video platform."""
        return self._detect_platform(url) is not None
    
    def _detect_platform(self, url: str) -> Optional[str]:
        """
        Detect which platform the URL belongs to.
        
        Returns: 'tiktok', 'instagram', 'youtube', or None
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
                
        return None

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
        # Only resolve known short URL patterns
        short_patterns = [
            r'tiktok\.com/t/',
            r'vm\.tiktok\.com/',
        ]
        
        needs_resolution = any(re.search(p, url.lower()) for p in short_patterns)
        
        if not needs_resolution:
            return (url, None)
            
        logger.info(f"Resolving short URL: {url}")
        
        try:
            # Follow redirects with a browser-like user agent
            headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
            }
            
            response = requests.head(
                url,
                headers=headers,
                allow_redirects=True,
                timeout=15
            )
            
            resolved_url = response.url
            
            # Check if we landed on a valid video URL (not home/explore page)
            # Invalid redirects go to: /?_r=1, /explore, etc.
            invalid_patterns = [
                r'tiktok\.com/\?',        # Home page
                r'tiktok\.com/explore',    # Explore page  
                r'tiktok\.com/$',          # Root
            ]
            
            is_invalid = any(re.search(p, resolved_url) for p in invalid_patterns)
            
            if is_invalid:
                logger.warning(f"Short URL expired or invalid - redirected to: {resolved_url}")
                return (url, f"TikTok short link has expired or is invalid. The URL '{url}' redirected to the TikTok home page instead of a video. Please use the full video URL (e.g., tiktok.com/@username/video/1234567890)")
                
            if '@' in resolved_url and '/video/' in resolved_url:
                logger.info(f"Resolved short URL to video: {resolved_url}")
                return (resolved_url, None)
            
            logger.info(f"Resolved URL: {resolved_url}")
            return (resolved_url, None)
            
        except requests.RequestException as e:
            logger.warning(f"Failed to resolve short URL: {e}")
            return (url, None)  # Return original on failure, let yt-dlp try

    async def parse(self, url: str, **kwargs) -> ParseResult:
        """
        Parse a recipe from a video URL.
        
        Pipeline:
        1. Detect platform
        2. Download audio directly with yt-dlp (--extract-audio)
        3. Transcribe with Whisper API
        4. Parse transcript with GPT-4 to extract recipe
        
        Note: We download audio-only to minimize bandwidth, disk usage, and legal footprint.
        Video frames are only needed if OCR is required (not implemented yet).
        
        Args:
            url: Video URL (TikTok, Instagram, YouTube)
            **kwargs: Additional options
                - need_video_frames: bool - If True, download full video for OCR (default: False)

        Returns:
            ParseResult with recipe data or error information
        """
        start_time = time.time()
        temp_dir = None
        need_video_frames = kwargs.get('need_video_frames', False)
        
        try:
            # Step 1: Detect platform
            platform = self._detect_platform(url)
            if not platform:
                return ParseResult(
                    success=False,
                    error_code="UNSUPPORTED_PLATFORM",
                    error_message=f"URL not recognized as TikTok, Instagram, or YouTube: {url}",
                    parser_name=self.parser_name
                )
            
            logger.info(f"Detected platform: {platform} for URL: {url}")
            
            # Resolve short URLs (TikTok /t/... links)
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
            
            # Create temp directory for processing
            temp_dir = tempfile.mkdtemp(prefix="video_recipe_")
            audio_path = os.path.join(temp_dir, "audio.mp3")
            
            # Step 2: Download audio directly with yt-dlp (faster, smaller footprint)
            logger.info("Downloading audio with yt-dlp (audio-only mode)...")
            download_info = self._download_audio(resolved_url, audio_path)
            if not download_info.get('success'):
                return ParseResult(
                    success=False,
                    error_code="DOWNLOAD_FAILED",
                    error_message=download_info.get('error', 'Failed to download audio'),
                    parser_name=self.parser_name
                )
            
            # Step 3: Transcribe with Whisper
            logger.info("Transcribing audio with Whisper API...")
            transcript = self._transcribe_audio(audio_path)
            if not transcript:
                return ParseResult(
                    success=False,
                    error_code="TRANSCRIPTION_FAILED",
                    error_message="Failed to transcribe audio or no speech detected",
                    parser_name=self.parser_name
                )
            
            logger.info(f"Transcript ({len(transcript)} chars): {transcript[:200]}...")
            
            # Step 4: Parse transcript with GPT-4 to extract recipe
            logger.info("Parsing transcript with GPT-4...")
            recipe_data = self._parse_transcript_to_recipe(
                transcript=transcript,
                video_title=download_info.get('title', ''),
                video_description=download_info.get('description', ''),
                platform=platform,
                url=url
            )
            
            if not recipe_data:
                return ParseResult(
                    success=False,
                    error_code="RECIPE_EXTRACTION_FAILED",
                    error_message="Could not extract recipe from transcript. Video may not be a cooking video.",
                    parser_name=self.parser_name
                )
            
            # Calculate processing time and confidence
            processing_time_ms = int((time.time() - start_time) * 1000)
            warnings = self._generate_warnings(recipe_data)
            confidence_score = self._calculate_confidence(recipe_data)
            
            logger.info(f"Successfully parsed video recipe: {recipe_data.get('name', 'Unknown')}")
            
            return ParseResult(
                success=True,
                data=recipe_data,
                parser_name=self.parser_name,
                confidence_score=confidence_score,
                warnings=warnings
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

    def _download_audio(self, url: str, output_path: str) -> Dict[str, Any]:
        """
        Download audio directly using yt-dlp's audio-only mode.
        
        This is faster and more efficient than downloading full video + ffmpeg extraction.
        Uses: yt-dlp -f bestaudio --extract-audio --audio-format mp3
        
        Returns dict with success, title, description, error
        """
        try:
            # First, get video info (title, description) - this is a lightweight metadata fetch
            info_cmd = [
                'yt-dlp',
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
            
            download_cmd = [
                'yt-dlp',
                '-f', 'bestaudio/best',  # Best audio stream
                '--extract-audio',  # Extract audio
                '--audio-format', 'mp3',  # Convert to mp3
                '--audio-quality', '64K',  # 64kbps is enough for speech
                '-o', output_template + '.%(ext)s',  # Let yt-dlp handle extension
                '--no-warnings',
                '--no-playlist',
                '--postprocessor-args', 'ffmpeg:-ar 16000 -ac 1',  # 16kHz mono for Whisper
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
            info_cmd = [
                'yt-dlp',
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
            download_cmd = [
                'yt-dlp',
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
        video_metadata: Optional[Dict] = None
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

        Returns:
            Recipe dict with standard structure, or None if not a recipe video

        Raises:
            Exception: If GPT-4 Vision API call fails after retries
        """
        if not frames:
            logger.warning("No frames provided for vision extraction")
            return None

        metadata = video_metadata or {}
        platform = metadata.get('platform', 'unknown')
        title = metadata.get('title', '')
        description = metadata.get('description', '')

        logger.info(f"Extracting recipe from {len(frames)} frames using GPT-4 Vision...")

        # Build the prompt
        prompt = self._build_vision_prompt(
            platform=platform,
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
