import os
import io
import json
import uuid
from datetime import datetime
import urllib.request
from PIL import Image, ImageDraw, ImageFont

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

def draw_grid(draw, width, height):
    """繪製 Cyberpunk 科技網格"""
    grid_color = (0, 255, 255, 25) # 半透明青色
    step = 20
    # 左下網格
    for x in range(0, 250, step):
        draw.line([(x, 750), (x, height)], fill=grid_color, width=1)
    for y in range(750, height, step):
        draw.line([(0, y), (250, y)], fill=grid_color, width=1)
        
    # 右下網格
    for x in range(550, width, step):
        draw.line([(x, 750), (x, height)], fill=grid_color, width=1)
    for y in range(750, height, step):
        draw.line([(550, y), (width, y)], fill=grid_color, width=1)

def create_rounded_rect(width, height, radius, fill_color, border_color, border_width=4):
    """建立帶有邊框與圓角的透明圖層"""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [(border_width, border_width), (width - border_width, height - border_width)],
        radius=radius,
        fill=fill_color,
        outline=border_color,
        width=border_width
    )
    return img

def generate_ig_card(user_id, title, prob, valuation, image_bytes, output_dir="cards"):
    """
    動態生成 Liquid Glass 風格的 Instagram Profile Card 健檢結果圖
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. 建立底圖畫布 (800 x 1000, 科技深藍底)
    width, height = 800, 1000
    base_img = Image.new("RGBA", (width, height), (5, 11, 26, 255))
    draw = ImageDraw.Draw(base_img, "RGBA")

    # 2. 繪製 Cyberpunk 網格背景
    draw_grid(draw, width, height)

    # 3. 繪製 Liquid Glass 主外框 (位置: 60, 60 到 740, 620)
    # 半透明深海藍填充 + 青色發光邊框
    glass_rect = create_rounded_rect(680, 560, radius=35, fill_color=(15, 43, 72, 190), border_color=(0, 200, 255, 255), border_width=4)
    base_img.paste(glass_rect, (60, 60), glass_rect)

    # 4. 文字寫入設定
    font_sm = get_font(22)
    font_md = get_font(28)
    font_lg = get_font(36)
    font_xl = get_font(46)
    font_xxl = get_font(54)

    # 5. 頂部 A.A.D Header 與品名
    # 置中計算小助手
    def draw_centered_text(draw, text, y, font, color):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        draw.text(((width - text_w) // 2, y), text, font=font, fill=color)

    draw_centered_text(draw, "A.A.D", 90, font_xxl, (0, 255, 255, 255))
    draw_centered_text(draw, title, 170, font_xl, (255, 255, 255, 255))

    # 6. Authenticity 機率框
    auth_text = f"AUTHENTICITY : {prob}"
    auth_rect = create_rounded_rect(560, 100, radius=15, fill_color=(0, 150, 255, 50), border_color=(0, 255, 255, 255), border_width=3)
    base_img.paste(auth_rect, (120, 260), auth_rect)
    draw_centered_text(draw, auth_text, 280, font_lg, (0, 255, 255, 255))

    # 7. 圓形文物照片遮罩處理 (放置於左中下 80, 420)
    circle_size = 400
    try:
        if image_bytes:
            user_photo = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        else:
            user_photo = Image.new("RGBA", (circle_size, circle_size), (40, 40, 40, 255))
            
        # 縮放裁剪成正方形
        w, h = user_photo.size
        min_dim = min(w, h)
        user_photo = user_photo.crop(((w - min_dim) // 2, (h - min_dim) // 2, (w + min_dim) // 2, (h + min_dim) // 2))
        user_photo = user_photo.resize((circle_size, circle_size), Image.Resampling.LANCZOS)
        
        # 建立圓形遮罩
        mask = Image.new("L", (circle_size, circle_size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse((0, 0, circle_size, circle_size), fill=255)
        
        # 套用遮罩並貼上
        circle_img = Image.new("RGBA", (circle_size, circle_size), (0, 0, 0, 0))
        circle_img.paste(user_photo, (0, 0), mask)
        base_img.paste(circle_img, (80, 420), circle_img)
    except Exception as e:
        print(f"User image process error: {e}")

    # 繪製圓形青色邊框
    draw.ellipse([(76, 416), (80 + circle_size + 4, 420 + circle_size + 4)], outline=(0, 255, 255, 255), width=8)

    # 8. 操作者資訊 (右側)
    draw.text((510, 580), "VIP 藏家", font=font_lg, fill=(255, 255, 255, 255))
    draw.text((510, 630), "健檢操作者", font=font_md, fill=(0, 170, 255, 255))

    # 9. 底部資訊欄
    # 日期
    date_str = datetime.now().strftime("%d %b %Y").upper()
    draw.text((80, 860), date_str, font=font_md, fill=(255, 255, 255, 255))
    draw.text((80, 905), "Ai Antique Diagnosis", font=font_sm, fill=(136, 170, 170, 255))

    # 箭頭符號
    draw.text((360, 860), ">>>>", font=font_lg, fill=(0, 255, 255, 255))

    # 估值
    draw.text((510, 820), "Price Valuation", font=font_md, fill=(255, 255, 255, 255))
    draw.text((510, 860), valuation, font=font_lg, fill=(0, 255, 255, 255))
    draw.text((510, 905), "若為真品之估值", font=font_sm, fill=(0, 170, 255, 255))

    # 10. 存檔回傳
    card_filename = f"card_{uuid.uuid4().hex[:12]}.png"
    card_path = os.path.join(output_dir, card_filename)
    base_img.convert("RGB").save(card_path, "PNG")
    
    return card_filename
