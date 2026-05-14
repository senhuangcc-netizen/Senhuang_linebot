import os
import io
import json
import uuid
import math
from datetime import datetime
import urllib.request
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# 字型設定 (自動下載 NotoSansTC 確保中文正常顯示)
FONT_PATH = "NotoSansTC-Bold.otf"
FONT_URL = "https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/TraditionalChinese/NotoSansCJKtc-Bold.otf"

def get_font(size):
    try:
        if not os.path.exists(FONT_PATH):
            print(f"Downloading font from {FONT_URL}...")
            urllib.request.urlretrieve(FONT_URL, FONT_PATH)
        return ImageFont.truetype(FONT_PATH, size)
    except Exception as e:
        print(f"Font loading error: {e}")
        return ImageFont.load_default()

def draw_gradient_background(width, height):
    """繪製深色放射狀漸層背景"""
    base = Image.new('RGBA', (width, height), (10, 15, 30, 255))
    draw = ImageDraw.Draw(base)
    
    # 中心點
    cx, cy = width // 2, height // 2
    max_radius = math.hypot(cx, cy)
    
    # 畫同心圓來模擬漸層
    gradient = Image.new('RGBA', (width, height), (0,0,0,0))
    grad_draw = ImageDraw.Draw(gradient)
    
    for r in range(int(max_radius), 0, -10):
        # 中心亮深藍 (25, 40, 70), 外圍深藍 (10, 15, 30)
        ratio = r / max_radius
        c = (
            int(10 + (25 - 10) * (1 - ratio)),
            int(15 + (40 - 15) * (1 - ratio)),
            int(30 + (70 - 30) * (1 - ratio)),
            255
        )
        grad_draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=c)
        
    gradient = gradient.filter(ImageFilter.GaussianBlur(20))
    base.paste(gradient, (0,0), gradient)
    return base

def draw_noise(img, intensity=10):
    """添加微弱雜訊增加質感"""
    import random
    noise = Image.new('RGBA', img.size, (0,0,0,0))
    pixels = noise.load()
    for y in range(img.height):
        for x in range(img.width):
            if random.random() < 0.1: # 只在10%的點加上雜訊
                val = random.randint(0, intensity)
                pixels[x, y] = (255, 255, 255, val)
    return Image.alpha_composite(img, noise)

def draw_dot_grid(draw, width, height):
    """繪製精緻的點狀網格"""
    dot_color = (255, 255, 255, 15)
    step = 30
    for x in range(0, width, step):
        for y in range(0, height, step):
            draw.point((x, y), fill=dot_color)

def create_rounded_rect(width, height, radius, fill_color, border_color, border_width=2, blur_radius=0):
    """建立帶有邊框與圓角的透明圖層，支援背景模糊模擬"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [(border_width, border_width), (width - border_width, height - border_width)],
        radius=radius,
        fill=fill_color,
        outline=border_color,
        width=border_width
    )
    if blur_radius > 0:
         img = img.filter(ImageFilter.GaussianBlur(blur_radius))
    return img

def generate_ig_card(user_id, title, prob, valuation, image_bytes, output_dir="cards"):
    """
    動態生成具備高級質感的 Instagram Profile Card
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. 建立底圖畫布 (800 x 1000)
    width, height = 800, 1000
    base_img = draw_gradient_background(width, height)
    base_img = draw_noise(base_img, intensity=15)
    
    draw = ImageDraw.Draw(base_img, "RGBA")

    # 2. 繪製點狀網格背景
    draw_dot_grid(draw, width, height)

    # 3. 繪製高質感毛玻璃主層 (Liquid Glass)
    # 底部光暈
    glow = create_rounded_rect(700, 880, radius=40, fill_color=(0, 200, 255, 15), border_color=(0,0,0,0), border_width=0, blur_radius=30)
    base_img.paste(glow, (50, 60), glow)
    
    # 主玻璃板
    glass_rect = create_rounded_rect(700, 880, radius=40, fill_color=(255, 255, 255, 10), border_color=(255, 255, 255, 40), border_width=2)
    base_img.paste(glass_rect, (50, 60), glass_rect)

    # 內部裝飾線
    draw.line([(90, 160), (710, 160)], fill=(255, 255, 255, 30), width=1)
    draw.line([(90, 750), (710, 750)], fill=(255, 255, 255, 30), width=1)

    # 4. 文字寫入設定
    font_xs = get_font(18)
    font_sm = get_font(24)
    font_md = get_font(30)
    font_lg = get_font(38)
    font_xl = get_font(48)
    font_xxl = get_font(60)

    # 5. 頂部 Header 與品名
    def draw_centered_text(draw, text, y, font, color):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text(((width - text_w) // 2, y), text, font=font, fill=color)

    # 標題區
    draw_centered_text(draw, "A.A.D SYSTEM", 85, font_sm, (0, 255, 255, 200))
    draw_centered_text(draw, "AI ANTIQUE DIAGNOSIS", 125, font_xs, (255, 255, 255, 120))
    
    # 品名區
    draw_centered_text(draw, title, 200, font_xl, (255, 255, 255, 255))

    # 6. 機率框 (質感提升)
    auth_rect = create_rounded_rect(580, 100, radius=20, fill_color=(0, 255, 255, 15), border_color=(0, 255, 255, 80), border_width=2)
    base_img.paste(auth_rect, (110, 300), auth_rect)
    
    auth_label = "AUTHENTICITY MATCH"
    bbox = draw.textbbox((0, 0), auth_label, font=font_sm)
    draw.text((150, 335), auth_label, font=font_sm, fill=(255, 255, 255, 200))
    
    draw.text((480, 320), prob, font=font_xxl, fill=(0, 255, 255, 255))

    # 7. 圓形文物照片
    circle_size = 280
    try:
        if image_bytes:
            user_photo = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        else:
            user_photo = Image.new("RGBA", (circle_size, circle_size), (40, 40, 40, 255))
            
        w, h = user_photo.size
        min_dim = min(w, h)
        user_photo = user_photo.crop(((w - min_dim) // 2, (h - min_dim) // 2, (w + min_dim) // 2, (h + min_dim) // 2))
        user_photo = user_photo.resize((circle_size, circle_size), Image.Resampling.LANCZOS)
        
        mask = Image.new("L", (circle_size, circle_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, circle_size, circle_size), fill=255)
        
        circle_img = Image.new("RGBA", (circle_size, circle_size), (0, 0, 0, 0))
        circle_img.paste(user_photo, (0, 0), mask)
        base_img.paste(circle_img, (110, 440), circle_img)
        
        # 繪製照片光暈與邊框
        draw.ellipse([(108, 438), (110 + circle_size + 2, 440 + circle_size + 2)], outline=(255, 255, 255, 100), width=4)
        draw.ellipse([(100, 430), (110 + circle_size + 10, 440 + circle_size + 10)], outline=(0, 255, 255, 50), width=1)
        
    except Exception as e:
        print(f"User image process error: {e}")

    # 8. 資訊標籤 (放置於照片右側)
    info_x = 440
    draw.text((info_x, 460), "CLIENT LEVEL", font=font_xs, fill=(255, 255, 255, 120))
    draw.text((info_x, 485), "VIP Collector", font=font_md, fill=(212, 175, 55, 255)) # 金色
    
    date_str = datetime.now().strftime("%d %b %Y").upper()
    draw.text((info_x, 560), "DIAGNOSIS DATE", font=font_xs, fill=(255, 255, 255, 120))
    draw.text((info_x, 585), date_str, font=font_md, fill=(255, 255, 255, 255))

    draw.text((info_x, 660), "REPORT ID", font=font_xs, fill=(255, 255, 255, 120))
    draw.text((info_x, 685), f"#{uuid.uuid4().hex[:8].upper()}", font=font_md, fill=(0, 255, 255, 255))

    # 9. 底部估值區
    draw_centered_text(draw, "MARKET VALUATION", 780, font_sm, (255, 255, 255, 150))
    draw_centered_text(draw, valuation, 820, font_xl, (212, 175, 55, 255)) # 高貴金色
    draw_centered_text(draw, "* Estimated value if confirmed authentic by physical inspection", 890, font_xs, (255, 255, 255, 80))

    # 10. 存檔回傳
    card_filename = f"card_{uuid.uuid4().hex[:12]}.png"
    card_path = os.path.join(output_dir, card_filename)
    base_img.convert("RGB").save(card_path, "PNG")
    
    return card_filename
