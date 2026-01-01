#!/usr/bin/env python3
"""
Generate app icon for Digital Mirror
Creates a simple mirror-style icon and converts to .icns format
"""

import os
import subprocess
from pathlib import Path

def create_icon_with_pillow():
    """Create icon using Pillow (if available)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("Pillow not installed. Installing...")
        subprocess.run(["pip", "install", "Pillow"], check=True)
        from PIL import Image, ImageDraw, ImageFont
    
    # Create assets directory
    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    # Icon sizes needed for .icns
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    
    def create_mirror_icon(size):
        """Create a mirror-themed icon at the given size."""
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Calculate dimensions
        margin = size // 10
        border_width = max(2, size // 50)
        
        # Draw mirror frame (rounded rectangle simulation)
        frame_color = (80, 80, 90)  # Dark gray frame
        mirror_color = (200, 220, 240)  # Light blue-ish mirror
        highlight_color = (255, 255, 255, 180)  # White highlight
        
        # Outer frame
        draw.rounded_rectangle(
            [margin, margin, size - margin, size - margin],
            radius=size // 8,
            fill=frame_color
        )
        
        # Inner mirror surface
        inner_margin = margin + border_width * 2
        draw.rounded_rectangle(
            [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
            radius=size // 10,
            fill=mirror_color
        )
        
        # Add gradient-like highlight (simplified)
        highlight_margin = inner_margin + size // 20
        highlight_width = size // 4
        highlight_height = size // 3
        
        # Create a subtle highlight ellipse
        for i in range(5):
            alpha = 150 - i * 30
            offset = i * 2
            draw.ellipse(
                [
                    highlight_margin + offset,
                    highlight_margin + offset,
                    highlight_margin + highlight_width - offset,
                    highlight_margin + highlight_height - offset
                ],
                fill=(255, 255, 255, max(0, alpha))
            )
        
        return img
    
    # Generate icons for all sizes
    iconset_dir = assets_dir / "icon.iconset"
    iconset_dir.mkdir(exist_ok=True)
    
    for size in sizes:
        icon = create_mirror_icon(size)
        
        # Save 1x version
        if size <= 512:
            icon.save(iconset_dir / f"icon_{size}x{size}.png")
        
        # Save 2x version (for Retina)
        if size >= 32:
            half_size = size // 2
            if half_size in [16, 32, 128, 256, 512]:
                icon.save(iconset_dir / f"icon_{half_size}x{half_size}@2x.png")
    
    print(f"✅ Icon images created in {iconset_dir}")
    return iconset_dir


def convert_to_icns(iconset_dir):
    """Convert iconset to .icns file using macOS iconutil."""
    assets_dir = iconset_dir.parent
    icns_path = assets_dir / "icon.icns"
    
    try:
        result = subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"✅ Created {icns_path}")
            return icns_path
        else:
            print(f"⚠️  iconutil failed: {result.stderr}")
            print("   You may need to run this on macOS")
            return None
            
    except FileNotFoundError:
        print("⚠️  iconutil not found (only available on macOS)")
        print(f"   PNG icons are in: {iconset_dir}")
        print("   On macOS, run: iconutil -c icns assets/icon.iconset -o assets/icon.icns")
        return None


def create_simple_png_icon():
    """Create a simple PNG icon as fallback (no dependencies)."""
    assets_dir = Path(__file__).parent / "assets"
    assets_dir.mkdir(exist_ok=True)
    
    # Create a simple SVG and note for the user
    svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg width="512" height="512" viewBox="0 0 512 512" xmlns="http://www.w3.org/2000/svg">
  <!-- Background circle -->
  <circle cx="256" cy="256" r="240" fill="#2a2a2a"/>
  
  <!-- Mirror frame -->
  <rect x="100" y="80" width="312" height="352" rx="40" fill="#505058"/>
  
  <!-- Mirror surface -->
  <rect x="120" y="100" width="272" height="312" rx="30" fill="#c8daf0"/>
  
  <!-- Highlight -->
  <ellipse cx="200" cy="180" rx="60" ry="80" fill="white" opacity="0.4"/>
  
  <!-- Small reflection dots -->
  <circle cx="350" cy="350" r="15" fill="white" opacity="0.2"/>
</svg>'''
    
    svg_path = assets_dir / "icon.svg"
    with open(svg_path, 'w') as f:
        f.write(svg_content)
    
    print(f"✅ Created SVG icon at {svg_path}")
    print("\nTo create .icns on macOS:")
    print("1. Open icon.svg in Preview or an image editor")
    print("2. Export as PNG at 1024x1024")
    print("3. Use an online converter or 'iconutil' to create .icns")
    
    return svg_path


def main():
    print("🪞 Generating Digital Mirror app icon...\n")
    
    try:
        # Try to create with Pillow
        iconset_dir = create_icon_with_pillow()
        
        # Try to convert to .icns (macOS only)
        convert_to_icns(iconset_dir)
        
    except Exception as e:
        print(f"⚠️  Could not create icon with Pillow: {e}")
        print("   Creating simple SVG fallback...\n")
        create_simple_png_icon()
    
    print("\n✨ Icon generation complete!")


if __name__ == "__main__":
    main()
