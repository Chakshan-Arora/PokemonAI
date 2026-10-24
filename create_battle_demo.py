#!/usr/bin/env python3
"""
Generates:
1. battle_final_screen.png - Pixel-accurate in-game battle screen mockup with new background, Pokemon, and UI placements.
2. battle_final_annotated.png - Annotated design guide showing exact platform placement and UI anchors.
"""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

def create_demo():
    output_dir = "/Users/utsavshivhare/.gemini/antigravity/brain/57b25a24-49f7-4df8-b95d-0134961a3a86"
    bg_path = "Godot/syntax-error-26/assets/backgrounds/battle_meadow_3d.png"
    bg_img = Image.open(bg_path).convert("RGBA")
    canvas_w, canvas_h = 1152, 648

    def build_canvas(include_annotations=False):
        canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 255))
        canvas.paste(bg_img, (0, 0))

        # Soft ambient ground contact shadows under feet
        shadow_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw_shadow = ImageDraw.Draw(shadow_layer)
        # Opponent shadow (under feet at 880, 315)
        draw_shadow.ellipse([810, 305, 950, 325], fill=(15, 35, 10, 140))
        # Player shadow (under feet at 270, 470)
        draw_shadow.ellipse([190, 455, 350, 480], fill=(10, 30, 10, 150))
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=3))
        canvas = Image.alpha_composite(canvas, shadow_layer)

        # Sprites
        pidgey = Image.open("Godot/syntax-error-26/assets/sprites/pokemon/Pidgey_front.png").convert("RGBA")
        pikachu = Image.open("Godot/syntax-error-26/assets/sprites/pokemon/Pikachu_back.png").convert("RGBA")

        # Opponent: 160x160 at 800, 155
        opp_w, opp_h = 160, 160
        pidgey_s = pidgey.resize((opp_w, opp_h), Image.Resampling.NEAREST)
        canvas.paste(pidgey_s, (800, 155), pidgey_s)

        # Player: 200x200 at 170, 270
        pl_w, pl_h = 200, 200
        pikachu_s = pikachu.resize((pl_w, pl_h), Image.Resampling.NEAREST)
        canvas.paste(pikachu_s, (170, 270), pikachu_s)

        # UI Layer
        ui_layer = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(ui_layer)

        font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
        font_bold = ImageFont.truetype(font_path, 20)
        font_md = ImageFont.truetype(font_path, 16)
        font_sm = ImageFont.truetype(font_path, 13)
        font_lg = ImageFont.truetype(font_path, 22)

        # 1. OPPONENT HUD (Top-Left: 40, 40 to 390, 145)
        draw.rounded_rectangle([40, 40, 390, 145], radius=12, fill=(245, 248, 252, 235), outline=(90, 120, 155, 220), width=2)
        p_port_path = "Godot/syntax-error-26/assets/sprites/portraits/Pidgey.png"
        if os.path.exists(p_port_path):
            p_port = Image.open(p_port_path).convert("RGBA").resize((44, 44), Image.Resampling.LANCZOS)
            ui_layer.paste(p_port, (55, 52), p_port)

        draw.text((110, 50), "Wild Pidgey", font=font_bold, fill=(25, 30, 45, 255))
        draw.text((310, 52), "Lv. 3", font=font_md, fill=(80, 95, 120, 255))
        draw.rounded_rectangle([110, 85, 370, 102], radius=4, fill=(40, 45, 55, 220))
        draw.rounded_rectangle([112, 87, 368, 100], radius=3, fill=(56, 175, 105, 255))
        draw.text((110, 108), "HP: 18 / 18", font=font_sm, fill=(90, 105, 125, 255))

        # 2. PLAYER HUD (Mid-Right: 710, 345 to 1080, 455)
        draw.rounded_rectangle([710, 345, 1080, 455], radius=12, fill=(245, 248, 252, 235), outline=(90, 120, 155, 220), width=2)
        pk_port_path = "Godot/syntax-error-26/assets/sprites/portraits/Pikachu.png"
        if os.path.exists(pk_port_path):
            pk_port = Image.open(pk_port_path).convert("RGBA").resize((44, 44), Image.Resampling.LANCZOS)
            ui_layer.paste(pk_port, (725, 355), pk_port)

        draw.text((780, 352), "Pikachu", font=font_bold, fill=(25, 30, 45, 255))
        draw.text((880, 354), "[STEADY]", font=font_sm, fill=(50, 160, 80, 255))
        draw.text((1010, 354), "Lv. 5", font=font_md, fill=(80, 95, 120, 255))
        draw.rounded_rectangle([780, 385, 1060, 398], radius=4, fill=(40, 45, 55, 220))
        draw.rounded_rectangle([782, 387, 1058, 396], radius=3, fill=(56, 175, 105, 255))
        draw.text((975, 404), "25 / 25 HP", font=font_sm, fill=(60, 75, 95, 255))
        draw.rounded_rectangle([780, 425, 1060, 432], radius=3, fill=(40, 45, 55, 220))
        draw.rounded_rectangle([782, 427, 915, 430], radius=2, fill=(49, 130, 206, 255))
        draw.text((780, 436), "EXP", font=ImageFont.truetype(font_path, 10), fill=(80, 110, 160, 255))

        # 3. MESSAGE BOX (Bottom-Left: 40, 490 to 650, 625)
        draw.rounded_rectangle([40, 490, 650, 625], radius=14, fill=(20, 28, 42, 235), outline=(75, 105, 150, 220), width=2)
        draw.text((65, 530), "What will Pikachu do?", font=font_lg, fill=(245, 250, 255, 255))

        # 4. ACTION MENU (Bottom-Right: 680, 490 to 1090, 625)
        draw.rounded_rectangle([680, 490, 1090, 625], radius=14, fill=(20, 28, 42, 235), outline=(75, 105, 150, 220), width=2)

        btn_w = (1090 - 680 - 40) // 3
        btn_h = (625 - 490 - 30) // 2
        bx0 = 690
        by0 = 500

        buttons = [
            ("⚔️ FIGHT", (185, 45, 45, 240), (235, 95, 95, 220), 0, 0),
            ("🎒 BAG", (45, 125, 185, 240), (95, 175, 235, 220), 1, 0),
            ("⚡ POKÉMON", (45, 155, 95, 240), (95, 215, 145, 220), 2, 0),
            ("💬 TALK", (180, 120, 40, 240), (230, 170, 90, 220), 0, 1),
            ("🏃 RUN", (130, 80, 165, 240), (180, 130, 215, 220), 1, 1),
        ]

        for label, bg_c, border_c, col, row in buttons:
            x1 = bx0 + col * (btn_w + 10)
            y1 = by0 + row * (btn_h + 10)
            x2 = x1 + btn_w
            y2 = y1 + btn_h
            draw.rounded_rectangle([x1, y1, x2, y2], radius=8, fill=bg_c, outline=border_c, width=1)
            bbox = font_sm.getbbox(label)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.text((x1 + (btn_w - tw)//2, y1 + (btn_h - th)//2 - 2), label, font=font_sm, fill=(255, 255, 255, 255))

        if include_annotations:
            draw.rounded_rectangle([40, 15, 240, 38], radius=4, fill=(0, 120, 180, 240))
            draw.text((48, 18), "① Opponent HUD (Top-Left)", font=font_sm, fill=(255, 255, 255))
            draw.rounded_rectangle([40, 40, 390, 145], outline=(0, 220, 255, 230), width=2)

            draw.rounded_rectangle([760, 125, 1000, 148], radius=4, fill=(180, 40, 40, 240))
            draw.text((768, 128), "② Opponent Base (Mid-Right)", font=font_sm, fill=(255, 255, 255))
            draw.rounded_rectangle([800, 155, 960, 315], outline=(255, 80, 80, 230), width=2)

            draw.rounded_rectangle([710, 320, 910, 343], radius=4, fill=(180, 140, 0, 240))
            draw.text((718, 323), "③ Player HUD (Mid-Right)", font=font_sm, fill=(255, 255, 255))
            draw.rounded_rectangle([710, 345, 1080, 455], outline=(255, 200, 0, 230), width=2)

            draw.rounded_rectangle([170, 240, 410, 263], radius=4, fill=(30, 150, 60, 240))
            draw.text((178, 243), "④ Partner Base (Foreground Left)", font=font_sm, fill=(255, 255, 255))
            draw.rounded_rectangle([170, 270, 370, 470], outline=(80, 240, 120, 230), width=2)

            draw.rounded_rectangle([40, 465, 240, 488], radius=4, fill=(120, 60, 180, 240))
            draw.text((48, 468), "⑤ Battle Dialogue Prompt", font=font_sm, fill=(255, 255, 255))
            draw.rounded_rectangle([40, 490, 650, 625], outline=(180, 120, 255, 230), width=2)

            draw.rounded_rectangle([680, 465, 870, 488], radius=4, fill=(180, 60, 120, 240))
            draw.text((688, 468), "⑥ Action Command Menu", font=font_sm, fill=(255, 255, 255))
            draw.rounded_rectangle([680, 490, 1090, 625], outline=(255, 120, 180, 230), width=2)

        return Image.alpha_composite(canvas, ui_layer)

    gameplay_demo = build_canvas(include_annotations=False)
    gameplay_path = os.path.join(output_dir, "battle_final_screen.png")
    gameplay_demo.save(gameplay_path, format="PNG")

    annotated_demo = build_canvas(include_annotations=True)
    annotated_path = os.path.join(output_dir, "battle_final_annotated.png")
    annotated_demo.save(annotated_path, format="PNG")
    print(f"Saved {gameplay_path} and {annotated_path}")

if __name__ == "__main__":
    create_demo()
