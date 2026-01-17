#!/bin/bash

# Directory-Based Recipe URL Discovery and Image Capture
# Token-efficient approach: Boss discovers URLs + captures images, Workers process autonomously

echo "🗂️ DIRECTORY-BASED RECIPE DISCOVERY"
echo "Strategy: Cuisine directories → dish names → URL discovery → image capture → autonomous workers"
echo "=============================================================================="

# Configuration
CUISINES_DIR="cuisines"
DISCOVERED_URLS_DIR="discovered-urls"
IMAGES_DIR="recipe-images"
CACHED_CONFIG_FILE="config/discovered_search_urls.json"

# Load cached sites from actual config file
load_cached_sites() {
  if [[ ! -f "$CACHED_CONFIG_FILE" ]]; then
    echo "❌ Cached sites config not found: $CACHED_CONFIG_FILE"
    exit 1
  fi
  
  # Extract sites with high success rates from config
  CACHED_SITES=($(jq -r 'to_entries[] | select(.value.success_rate > 0.7) | .key' "$CACHED_CONFIG_FILE" 2>/dev/null))
  
  echo "📋 Loaded ${#CACHED_SITES[@]} high-success cached sites from config:"
  for site in "${CACHED_SITES[@]}"; do
    success_rate=$(jq -r ".\"$site\".success_rate" "$CACHED_CONFIG_FILE")
    echo "  • $site (success: $(echo "$success_rate * 100" | bc -l | cut -d. -f1)%)"
  done
}

# Setup directories
setup_directories() {
  echo "📁 Setting up directory structure..."
  
  mkdir -p "$DISCOVERED_URLS_DIR"
  mkdir -p "$IMAGES_DIR"
  
  # Create subdirectories for each cuisine in images
  for cuisine_dir in "$CUISINES_DIR"/*; do
    if [[ -d "$cuisine_dir" ]]; then
      cuisine_name=$(basename "$cuisine_dir")
      mkdir -p "$IMAGES_DIR/$cuisine_name"
      mkdir -p "$DISCOVERED_URLS_DIR/$cuisine_name"
    fi
  done
  
  echo "✅ Directory structure ready"
}

# Phase 1: Discover URLs for all dishes across all cuisines
discover_all_urls() {
  echo ""
  echo "🔍 PHASE 1: URL DISCOVERY FOR ALL DISHES"
  echo "============================================"
  
  total_dishes=0
  total_urls_found=0
  
  # Process each cuisine directory
  for cuisine_dir in "$CUISINES_DIR"/*; do
    if [[ ! -d "$cuisine_dir" ]]; then continue; fi
    
    cuisine_name=$(basename "$cuisine_dir")
    dish_file="$cuisine_dir/dish-names.txt"
    
    if [[ ! -f "$dish_file" ]]; then
      echo "⚠️ No dish-names.txt found for $cuisine_name"
      continue
    fi
    
    echo ""
    echo "🍽️ Processing $cuisine_name cuisine..."
    
    cuisine_urls_file="$DISCOVERED_URLS_DIR/$cuisine_name/recipe-urls.txt"
    > "$cuisine_urls_file"  # Clear file
    
    dishes_in_cuisine=0
    urls_for_cuisine=0
    
    # Process each dish in the cuisine
    while IFS= read -r dish_name || [[ -n "$dish_name" ]]; do
      # Clean dish name (remove any leading numbers or symbols)
      clean_dish=$(echo "$dish_name" | sed 's/^[0-9]*[→\-\.\s]*//' | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
      
      if [[ -z "$clean_dish" ]]; then continue; fi
      
      ((dishes_in_cuisine++))
      ((total_dishes++))
      
      echo "  🔍 Searching for: $clean_dish"
      
      # Try to find recipe URL using cached sites from config
      url_found=false
      
      for site in "${CACHED_SITES[@]}"; do
        echo "    🌐 Trying $site..."
        
        # Get search URL pattern from cached config
        search_pattern=$(jq -r ".\"$site\".search_urls[0] // empty" "$CACHED_CONFIG_FILE")
        
        if [[ -n "$search_pattern" ]]; then
          # Build complete search URL using cached pattern
          encoded_query=$(echo "$clean_dish" | sed 's/ /%20/g')
          search_url="https://$site${search_pattern/\{query\}/$encoded_query}"
          
          echo "    📋 Using cached pattern: $search_url"
          
          # Navigate to search page and extract HTML
          if mcp__playwright__browser_navigate "$search_url"; then
            sleep 3  # Let page load
            
            # Get page HTML and extract all links
            page_html=$(mcp__playwright__browser_evaluate --function="() => document.documentElement.outerHTML")
            
            if [[ $? -eq 0 ]] && [[ -n "$page_html" ]]; then
              echo "    🕷️ Extracted HTML, finding recipe URLs..."
              
              # Extract all URLs from HTML that look like recipe pages
              recipe_urls=$(echo "$page_html" | grep -oP 'href="[^"]*recipe[^"]*"' | grep -v search | grep -v category | head -5 | sed 's/href="//g' | sed 's/"//g')
              
              # Also try alternative patterns based on site
              if [[ -z "$recipe_urls" ]]; then
                case $site in
                  "allrecipes.com")
                    recipe_urls=$(echo "$page_html" | grep -oP 'href="[^"]*\/recipe\/[0-9]+\/[^"]*"' | head -3 | sed 's/href="//g' | sed 's/"//g')
                    ;;
                  "simplyrecipes.com")
                    recipe_urls=$(echo "$page_html" | grep -oP 'href="[^"]*\/recipes\/[^"]*"' | head -3 | sed 's/href="//g' | sed 's/"//g')
                    ;;
                  "delish.com"|"tasteofhome.com"|"foodandwine.com")
                    recipe_urls=$(echo "$page_html" | grep -oP 'href="[^"]*\/recipe[s]?\/[^"]*"' | head -3 | sed 's/href="//g' | sed 's/"//g')
                    ;;
                  *)
                    recipe_urls=$(echo "$page_html" | grep -oP 'href="[^"]*"' | grep -E "(recipe|Recipe)" | grep -v search | head -3 | sed 's/href="//g' | sed 's/"//g')
                    ;;
                esac
              fi
              
              # Process found URLs
              if [[ -n "$recipe_urls" ]]; then
                while IFS= read -r url; do
                  if [[ -z "$url" ]]; then continue; fi
                  
                  # Convert relative URLs to absolute
                  if [[ "$url" =~ ^/ ]]; then
                    full_url="https://$site$url"
                  elif [[ "$url" =~ ^http ]]; then
                    full_url="$url"
                  else
                    continue  # Skip invalid URLs
                  fi
                  
                  echo "    🔍 Found potential recipe URL: $full_url"
                  
                  # Take the first valid recipe URL found
                  echo "$full_url|$clean_dish|$cuisine_name|$site" >> "$cuisine_urls_file"
                  ((urls_for_cuisine++))
                  ((total_urls_found++))
                  echo "    ✅ Saved recipe URL: $full_url"
                  url_found=true
                  break  # Take first URL found
                  
                done <<< "$recipe_urls"
                
                if [[ "$url_found" == "true" ]]; then
                  break  # Found URL for this dish, move to next dish
                fi
              else
                echo "    ❌ No recipe URLs found in HTML"
              fi
            else
              echo "    ❌ Failed to extract HTML"
            fi
          else
            echo "    ❌ Failed to navigate to: $search_url"
          fi
        else
          echo "    ❌ No cached search pattern for $site"
        fi
        
        sleep 1  # Rate limiting between sites
      done
      
      if [[ "$url_found" == "false" ]]; then
        echo "    ❌ No recipe URL found for: $clean_dish"
      fi
      
    done < "$dish_file"
    
    echo "  📊 $cuisine_name results: $urls_for_cuisine URLs found for $dishes_in_cuisine dishes"
    
  done
  
  echo ""
  echo "📊 URL DISCOVERY COMPLETE:"
  echo "  • Total dishes processed: $total_dishes"
  echo "  • Total URLs found: $total_urls_found"
  echo "  • Success rate: $(( total_urls_found * 100 / total_dishes ))%"
}

# Phase 2: Capture images for all discovered URLs
capture_all_images() {
  echo ""
  echo "📸 PHASE 2: IMAGE CAPTURE FOR ALL DISCOVERED URLS"
  echo "=================================================="
  
  total_images_captured=0
  failed_captures=0
  
  # Process each cuisine's discovered URLs
  for cuisine_dir in "$DISCOVERED_URLS_DIR"/*; do
    if [[ ! -d "$cuisine_dir" ]]; then continue; fi
    
    cuisine_name=$(basename "$cuisine_dir")
    urls_file="$cuisine_dir/recipe-urls.txt"
    
    if [[ ! -f "$urls_file" ]]; then continue; fi
    
    echo ""
    echo "📸 Capturing images for $cuisine_name..."
    
    images_captured_for_cuisine=0
    
    while IFS='|' read -r recipe_url dish_name cuisine site; do
      if [[ -z "$recipe_url" ]]; then continue; fi
      
      echo "  📸 Capturing image for: $dish_name"
      echo "    🌐 URL: $recipe_url"
      
      # Create safe filename from dish name
      safe_filename=$(echo "$dish_name" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-\|-$//g')
      
      # Navigate to recipe page
      if mcp__playwright__browser_navigate "$recipe_url"; then
        sleep 3  # Let page load
        
        # Take screenshot of the recipe
        image_filename="$safe_filename.png"
        image_path="$IMAGES_DIR/$cuisine_name/$image_filename"
        
        if mcp__playwright__browser_take_screenshot \
          --filename="$image_path" \
          --fullPage=false; then
          
          echo "    ✅ Image captured: $image_path"
          
          # Create processing instruction file for worker
          instruction_file="$DISCOVERED_URLS_DIR/$cuisine_name/${safe_filename}-instruction.txt"
          cat > "$instruction_file" << EOF
$recipe_url
$dish_name
$cuisine_name
$site
$image_path
EOF
          
          ((images_captured_for_cuisine++))
          ((total_images_captured++))
          
        else
          echo "    ❌ Failed to capture image for: $dish_name"
          ((failed_captures++))
        fi
      else
        echo "    ❌ Failed to navigate to: $recipe_url"
        ((failed_captures++))
      fi
      
      sleep 2  # Rate limiting between page loads
      
    done < "$urls_file"
    
    echo "  📊 $cuisine_name: $images_captured_for_cuisine images captured"
    
  done
  
  echo ""
  echo "📊 IMAGE CAPTURE COMPLETE:"
  echo "  • Total images captured: $total_images_captured"
  echo "  • Failed captures: $failed_captures"
  echo "  • Success rate: $(( total_images_captured * 100 / (total_images_captured + failed_captures) ))%"
}

# Phase 3: Create worker instruction files
create_worker_instructions() {
  echo ""
  echo "📋 PHASE 3: CREATING WORKER INSTRUCTION FILES"
  echo "=============================================="
  
  # Create master worker file list
  master_file="worker-instructions-master.txt"
  > "$master_file"
  
  total_instructions=0
  
  for cuisine_dir in "$DISCOVERED_URLS_DIR"/*; do
    if [[ ! -d "$cuisine_dir" ]]; then continue; fi
    
    cuisine_name=$(basename "$cuisine_dir")
    
    echo "📋 Processing instructions for $cuisine_name..."
    
    instruction_count=0
    
    # Find all instruction files for this cuisine
    for instruction_file in "$cuisine_dir"/*-instruction.txt; do
      if [[ -f "$instruction_file" ]]; then
        echo "$instruction_file" >> "$master_file"
        ((instruction_count++))
        ((total_instructions++))
      fi
    done
    
    echo "  ✅ $cuisine_name: $instruction_count instruction files ready"
  done
  
  echo ""
  echo "📊 WORKER INSTRUCTIONS READY:"
  echo "  • Total instruction files: $total_instructions"
  echo "  • Master file: $master_file"
  echo "  • Each file contains: URL, dish name, cuisine, site, image path"
}

# Phase 4: Calculate worker distribution
calculate_worker_distribution() {
  echo ""
  echo "👥 PHASE 4: WORKER DISTRIBUTION CALCULATION"
  echo "==========================================="
  
  if [[ ! -f "worker-instructions-master.txt" ]]; then
    echo "❌ Master instruction file not found"
    return 1
  fi
  
  total_jobs=$(wc -l < "worker-instructions-master.txt")
  worker_count=4
  jobs_per_worker=$((total_jobs / worker_count))
  remainder=$((total_jobs % worker_count))
  
  echo "📊 Distribution calculation:"
  echo "  • Total jobs: $total_jobs"
  echo "  • Workers: $worker_count"
  echo "  • Jobs per worker: $jobs_per_worker"
  echo "  • Extra jobs: $remainder (distributed to first workers)"
  
  # Create worker-specific instruction files
  current_line=1
  
  for i in $(seq 1 $worker_count); do
    worker_jobs=$jobs_per_worker
    if [[ $i -le $remainder ]]; then
      ((worker_jobs++))
    fi
    
    worker_file="worker-${i}-instructions.txt"
    tail -n +$current_line "worker-instructions-master.txt" | head -n $worker_jobs > "$worker_file"
    
    echo "  ✅ Worker $i: $worker_jobs jobs assigned ($worker_file)"
    
    current_line=$((current_line + worker_jobs))
  done
  
  echo ""
  echo "🚀 READY FOR AUTONOMOUS WORKER DEPLOYMENT"
  echo "Workers can now process independently - no communication needed!"
}

# Main execution
main() {
  echo "🚀 Starting directory-based recipe discovery and image capture"
  echo "Target: All dishes across all cuisines with pre-captured images"
  echo ""
  
  # Execute all phases
  load_cached_sites
  setup_directories
  discover_all_urls
  capture_all_images  
  create_worker_instructions
  calculate_worker_distribution
  
  echo ""
  echo "🎉 DISCOVERY AND PREPARATION COMPLETE!"
  echo "=============================================="
  echo "✅ URLs discovered and saved by cuisine"
  echo "✅ Images pre-captured for all recipes"
  echo "✅ Worker instruction files created"
  echo "✅ Workers can now run autonomously"
  echo ""
  echo "📋 Next Steps:"
  echo "  1. Launch autonomous workers: ./launch-autonomous-worker.sh 1"
  echo "  2. Each worker processes independently (no communication overhead)"
  echo "  3. Monitor progress by checking worker log files"
  echo ""
  echo "🎯 Expected: 500-1000 recipes processed with minimal token usage!"
}

# Handle interrupts
trap 'echo ""; echo "🛑 Discovery interrupted. Progress saved."; exit 1' INT

# Execute main function
main "$@"