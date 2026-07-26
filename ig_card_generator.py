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
    grid_color = (0, 255, 255, 18)
    step = 20
    # 左下網格
    for x in range(0, 250, step):
        draw.line([(x, 800), (x, height)], fill=grid_color, width=1)
    for y in range(800, height, step):
        draw.line([(0, y), (250, y)], fill=grid_color, width=1)
    # 右下網格
    for x in range(550, width, step):
        draw.line([(x, 800), (x, height)], fill=grid_color, width=1)
    for y in range(800, height, step):
        draw.line([(550, y), (width, y)], fill=grid_color, width=1)

def draw_sci_fi_panel(draw, width, height, fill_color, border_color, outer_width=4):
    """
    繪製科技感切角雙邊框面版 (HUD Panel)
    自適應寬高，左右各留 100px 邊距，上下各留 50px
    """
    lx, rx = 50, width - 50
    ty, by = 50, height - 50
    c = 35
    vertices_outer = [
        (lx + c, ty),
        (rx - c, ty),
        (rx, ty + c),
        (rx, by - c),
        (rx - c, by),
        (lx + c, by),
        (lx, by - c),
        (lx, ty + c),
    ]
    draw.polygon(vertices_outer, fill=fill_color, outline=border_color, width=outer_width)
    # 內層裝飾邊框
    vertices_inner = [
        (lx + c + 4, ty + 8),
        (rx - c - 4, ty + 8),
        (rx - 8, ty + c + 4),
        (rx - 8, by - c - 4),
        (rx - c - 4, by - 8),
        (lx + c + 4, by - 8),
        (lx + 8, by - c - 4),
        (lx + 8, ty + c + 4),
    ]
    draw.polygon(vertices_inner, fill=None, outline=(0, 255, 255, 60), width=1)

    # 側邊括號裝飾
    mid_y = (ty + by) // 2
    bracket_half = 120
    draw.line([(lx - 50, mid_y - bracket_half), (lx - 50, mid_y + bracket_half)], fill=(0, 200, 255, 80), width=2)
    draw.line([(lx - 70, mid_y - bracket_half), (lx - 50, mid_y - bracket_half)], fill=(0, 200, 255, 80), width=2)
    draw.line([(lx - 70, mid_y + bracket_half), (lx - 50, mid_y + bracket_half)], fill=(0, 200, 255, 80), width=2)
    draw.line([(rx + 50, mid_y - bracket_half), (rx + 50, mid_y + bracket_half)], fill=(0, 200, 255, 80), width=2)
    draw.line([(rx + 50, mid_y - bracket_half), (rx + 70, mid_y - bracket_half)], fill=(0, 200, 255, 80), width=2)
    draw.line([(rx + 50, mid_y + bracket_half), (rx + 70, mid_y + bracket_half)], fill=(0, 200, 255, 80), width=2)
    # 橫向輔助線
    draw.line([(0, mid_y), (lx, mid_y)], fill=(0, 200, 255, 60), width=2)
    draw.line([(rx, mid_y), (width, mid_y)], fill=(0, 200, 255, 60), width=2)

def generate_ig_card(user_id, title, prob, valuation, image_bytes, output_dir="cards", user_name="VIP 藏家"):
    """
    依據用戶設計圖樣板，動態生成極具未來科技感的 A.A.D 文物健檢圖卡
    全新版：照片置中於上方，所有文字資訊清楚排列於下方，確保無重疊
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    width, height = 800, 1160
    base_img = Image.new("RGBA", (width, height), (5, 11, 26, 255))
    draw = ImageDraw.Draw(base_img, "RGBA")

    # === 背景裝飾 ===
    draw_grid(draw, width, height)
    draw_sci_fi_panel(draw, width, height, fill_color=(12, 32, 59, 200), border_color=(0, 200, 255, 255), outer_width=4)

    # === 字型 ===
    font_sm = get_font(22)
    font_md = get_font(26)
    font_lg = get_font(32)
    font_xl = get_font(40)
    font_xxl = get_font(54)
    font_prob = get_font(64)

    def draw_centered_text(text, y, font, color, shadow_color=None, offset=2):
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        x_pos = (width - text_w) // 2
        if shadow_color:
            draw.text((x_pos - offset, y + offset), text, font=font, fill=shadow_color)
        draw.text((x_pos, y), text, font=font, fill=color)

    # === 區塊 1：頂部標題 (y: 70~220) ===
    draw_centered_text("A.A.D", 72, font_xxl, (255, 255, 255, 255), shadow_color=(0, 255, 255, 200), offset=2)

    # 品名框
    title_box_top = 148
    draw.rectangle([(160, title_box_top), (640, title_box_top + 65)], fill=(0, 20, 55, 220), outline=(0, 200, 255, 200), width=2)
    draw_centered_text(title, title_box_top + 10, font_xl, (255, 255, 255, 255))

    # === 區塊 2：圓形照片 — 居中，y: 230~590 ===
    circle_size = 360
    circle_x = (width - circle_size) // 2  # 220
    circle_y = 228

    try:
        if image_bytes:
            user_photo = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        else:
            user_photo = Image.new("RGBA", (circle_size, circle_size), (40, 40, 40, 255))

        w, h = user_photo.size
        min_dim = min(w, h)
        user_photo = user_photo.crop(((w - min_dim)//2, (h - min_dim)//2, (w + min_dim)//2, (h + min_dim)//2))
        user_photo = user_photo.resize((circle_size, circle_size), Image.Resampling.LANCZOS)

        mask = Image.new("L", (circle_size, circle_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, circle_size, circle_size), fill=255)
        circle_img = Image.new("RGBA", (circle_size, circle_size), (0, 0, 0, 0))
        circle_img.paste(user_photo, (0, 0), mask)
        base_img.paste(circle_img, (circle_x, circle_y), circle_img)
    except Exception as e:
        print(f"User image process error: {e}")

    # 圓形發光外框
    pad = 7
    draw.ellipse([(circle_x - pad, circle_y - pad),
                  (circle_x + circle_size + pad, circle_y + circle_size + pad)],
                 outline=(0, 255, 255, 255), width=7)
    draw.ellipse([(circle_x - pad - 8, circle_y - pad - 8),
                  (circle_x + circle_size + pad + 8, circle_y + circle_size + pad + 8)],
                 outline=(0, 255, 255, 50), width=2)

    # === 區塊 3：真品機率 — 照片正下方 y: 610~710 ===
    rate_y = circle_y + circle_size + 30  # ≈ 618
    draw_centered_text("AUTHENTICITY", rate_y, font_lg, (100, 200, 255, 255))
    draw_centered_text(prob, rate_y + 45, font_prob, (255, 255, 255, 255), shadow_color=(0, 255, 255, 200), offset=3)

    # === 分隔線 ===
    sep1_y = rate_y + 135
    draw.line([(120, sep1_y), (680, sep1_y)], fill=(0, 200, 255, 120), width=1)

    # === 區塊 4：健檢操作者 ===
    op_y = sep1_y + 20
    draw_centered_text(user_name, op_y, font_lg, (255, 255, 255, 255))
    draw_centered_text("健檢操作者", op_y + 44, font_md, (0, 180, 255, 255))

    # === 分隔線 ===
    sep2_y = op_y + 100
    draw.line([(120, sep2_y), (680, sep2_y)], fill=(0, 200, 255, 70), width=1)

    # === 區塊 5：底部三欄 (日期 | 箭頭 | 估值) ===
    btm_y = sep2_y + 22

    # 左：日期
    date_str = datetime.now().strftime("%Y-%m-%d")
    draw.text((120, btm_y), date_str, font=font_md, fill=(255, 255, 255, 255))
    draw.text((120, btm_y + 40), "Ai Antique Diagnosis", font=font_sm, fill=(110, 160, 160, 255))

    # 中：箭頭
    arr_bbox = draw.textbbox((0, 0), ">>>>", font=font_lg)
    arr_w = arr_bbox[2] - arr_bbox[0]
    draw.text(((width - arr_w) // 2, btm_y + 8), ">>>>", font=font_lg, fill=(0, 255, 255, 255))

    # 右：估值 (拆成兩行避免超出右側邊框)
    draw.text((460, btm_y - 28), "Price Valuation", font=font_md, fill=(200, 220, 255, 255))
    if "~" in valuation:
        val_parts = valuation.split("~", 1)
        draw.text((460, btm_y + 6),  val_parts[0].rstrip() + "~", font=font_lg, fill=(0, 255, 255, 255))
        draw.text((460, btm_y + 44), val_parts[1].lstrip(),        font=font_lg, fill=(0, 255, 255, 255))
        draw.text((460, btm_y + 82), "若為真品之估值", font=font_sm, fill=(0, 170, 255, 255))
    else:
        draw.text((460, btm_y + 6),  valuation, font=font_lg, fill=(0, 255, 255, 255))
        draw.text((460, btm_y + 44), "若為真品之估值", font=font_sm, fill=(0, 170, 255, 255))

    # === 存檔 ===
    card_filename = f"card_{uuid.uuid4().hex[:12]}.png"
    card_path = os.path.join(output_dir, card_filename)
    base_img.convert("RGB").save(card_path, "PNG")

    return card_filename
