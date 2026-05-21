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
    grid_color = (0, 255, 255, 20) # 更加溫和的半透明青色
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

def draw_sci_fi_panel(draw, fill_color, border_color, outer_width=4):
    """
    繪製科技感切角雙邊框面版 (HUD Panel)
    寬度: 150 到 650, 高度: 60 到 580 (切角大小 c=35)
    """
    c = 35
    # 外層邊框多邊形頂點
    vertices_outer = [
        (150 + c, 60),
        (650 - c, 60),
        (650, 60 + c),
        (650, 580 - c),
        (650 - c, 580),
        (150 + c, 580),
        (150, 580 - c),
        (150, 60 + c),
    ]
    draw.polygon(vertices_outer, fill=fill_color, outline=border_color, width=outer_width)

    # 內層裝飾邊框 (略微向內縮小 8px)
    vertices_inner = [
        (150 + c + 4, 60 + 8),
        (650 - c - 4, 60 + 8),
        (650 - 8, 60 + c + 4),
        (650 - 8, 580 - c - 4),
        (650 - c - 4, 580 - 8),
        (150 + c + 4, 580 - 8),
        (150 + 8, 580 - c - 4),
        (150 + 8, 60 + c + 4),
    ]
    draw.polygon(vertices_inner, fill=None, outline=(0, 255, 255, 60), width=1)

    # 繪製橫向與縱向的科技輔助線/括號裝飾
    # 橫向橫貫線
    draw.line([(0, 320), (150, 320)], fill=(0, 200, 255, 80), width=2)
    draw.line([(650, 320), (800, 320)], fill=(0, 200, 255, 80), width=2)
    
    # 兩側括號裝飾
    draw.line([(100, 200), (100, 440)], fill=(0, 200, 255, 80), width=2)
    draw.line([(80, 200), (100, 200)], fill=(0, 200, 255, 80), width=2)
    draw.line([(80, 440), (100, 440)], fill=(0, 200, 255, 80), width=2)

    draw.line([(700, 200), (700, 440)], fill=(0, 200, 255, 80), width=2)
    draw.line([(700, 200), (720, 200)], fill=(0, 200, 255, 80), width=2)
    draw.line([(700, 440), (720, 440)], fill=(0, 200, 255, 80), width=2)

def generate_ig_card(user_id, title, prob, valuation, image_bytes, output_dir="cards", user_name="VIP 藏家"):
    """
    依據用戶設計圖樣板，動態生成極具未來科技感的 A.A.D 文物健檢圖卡
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 1. 建立底圖畫布 (800 x 1000, 科技深藍底)
    width, height = 800, 1000
    base_img = Image.new("RGBA", (width, height), (5, 11, 26, 255))
    draw = ImageDraw.Draw(base_img, "RGBA")

    # 2. 繪製背景網格
    draw_grid(draw, width, height)

    # 3. 繪製科技感切角雙邊框面版 (HUD Panel)
    # 半透明深藍填充 + 青色發光外框
    draw_sci_fi_panel(draw, fill_color=(12, 32, 59, 180), border_color=(0, 200, 255, 255), outer_width=4)

    # 4. 字型大小宣告
    font_sm = get_font(22)
    font_md = get_font(26)
    font_lg = get_font(32)
    font_xl = get_font(38)
    font_xxl = get_font(52)
    font_prob = get_font(56)

    # 5. 置中寫入文字輔助函式
    def draw_centered_text(draw, text, y, font, color, shadow_color=None, offset=2):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x_pos = (width - text_w) // 2
        if shadow_color:
            draw.text((x_pos - offset, y), text, font=font, fill=shadow_color)
        draw.text((x_pos, y), text, font=font, fill=color)

    # 6. A.A.D 頂部與品名標題 (加發光陰影)
    draw_centered_text(draw, "A.A.D", 80, font_xxl, (255, 255, 255, 255), shadow_color=(0, 255, 255, 255), offset=2)
    
    # 繪製品名外框
    title_box_y1, title_box_y2 = 155, 220
    draw.rectangle([(220, title_box_y1), (580, title_box_y2)], fill=None, outline=(0, 200, 255, 120), width=2)
    draw_centered_text(draw, title, 165, font_xl, (255, 255, 255, 255))

    # 7. AUTHENTICIT (真品機率)
    draw_centered_text(draw, "AUTHENTICIT :", 280, font_lg, (143, 219, 255, 255))
    draw_centered_text(draw, prob, 350, font_prob, (255, 255, 255, 255), shadow_color=(0, 255, 255, 255), offset=2)

    # 8. 圓形文物照片處理 (放置於左下 110, 390)
    circle_size = 380
    circle_x, circle_y = 110, 390
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
        base_img.paste(circle_img, (circle_x, circle_y), circle_img)
    except Exception as e:
        print(f"User image process error: {e}")

    # 繪製圓形發光外框 (科技青色)
    draw.ellipse([(circle_x - 5, circle_y - 5), (circle_x + circle_size + 5, circle_y + circle_size + 5)], outline=(0, 255, 255, 255), width=8)
    draw.ellipse([(circle_x - 12, circle_y - 12), (circle_x + circle_size + 12, circle_y + circle_size + 12)], outline=(0, 255, 255, 60), width=2)

    # 9. 健檢操作者 (右側)
    draw.text((510, 650), user_name, font=font_lg, fill=(255, 255, 255, 255))
    draw.text((510, 705), "健檢操作者", font=font_md, fill=(0, 170, 255, 255))

    # 10. 底部資訊欄
    # 日期
    date_str = datetime.now().strftime("%Y-%m-%d").upper()
    draw.text((110, 860), date_str, font=font_md, fill=(255, 255, 255, 255))
    draw.text((110, 905), "Ai Antique Diagnosis", font=font_sm, fill=(136, 170, 170, 255))

    # 箭頭符號
    draw.text((380, 865), ">>>>", font=font_lg, fill=(0, 255, 255, 255))

    # 估值
    draw.text((510, 820), "Price Valuation", font=font_md, fill=(255, 255, 255, 255))
    draw.text((510, 860), valuation, font=font_lg, fill=(0, 255, 255, 255))
    draw.text((510, 905), "若為真品之估值", font=font_sm, fill=(0, 170, 255, 255))

    # 11. 存檔回傳
    card_filename = f"card_{uuid.uuid4().hex[:12]}.png"
    card_path = os.path.join(output_dir, card_filename)
    base_img.convert("RGB").save(card_path, "PNG")
    
    return card_filename
