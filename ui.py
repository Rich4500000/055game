"""界面绘制模块。

DefenseUI 负责开始界面、雷达面板、任务简报、编队图、按钮与工具提示。
"""

import math
import os
import pygame

from config import (
    BLACK,
    BLUE,
    CYAN,
    DARK,
    FAILURE_PENALTY,
    GRAY,
    GREEN,
    GREEN_DIM,
    HHQ9B_RANGE_KM,
    HHQ16B_RANGE_KM,
    HEIGHT,
    ORANGE,
    ORGANIC_RADAR_RANGE_KM,
    PANEL,
    PANEL_EDGE,
    RADAR_CENTER,
    RADAR_RANGE_KM,
    RADAR_RADIUS,
    RED,
    SHIP_HEALTH,
    SHIP_INFO,
    TARGET_AIRCRAFT,
    TARGET_LAND,
    TARGET_MISSILE,
    TARGET_SEA,
    WHITE,
    VLS_TOTAL,
    WIDTH,
    YELLOW,
    YJ18_RANGE_KM,
    YJ21_RANGE_KM,
    CJ10_RANGE_KM,
    clamp,
    px_to_km,
)


class Button:
    """底部按钮，支持点击和鼠标悬停提示。"""

    def __init__(self, rect, text, tip, hotkey):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.tip = tip
        self.hotkey = hotkey

    def draw(self, surface, font, mouse_pos):
        hover = self.rect.collidepoint(mouse_pos)
        color = (28, 73, 82) if hover else PANEL
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, CYAN if hover else PANEL_EDGE, self.rect, 1, border_radius=6)
        label = font.render(self.text, True, WHITE)
        surface.blit(label, label.get_rect(center=self.rect.center))


class DefenseUI:
    """所有UI元素的统一绘制入口。"""

    def __init__(self):
        pygame.font.init()
        self.font_path = find_cjk_font()
        self.font = make_font(self.font_path, 18)
        self.small = make_font(self.font_path, 14)
        self.large = make_font(self.font_path, 34, bold=True)
        self.mid = make_font(self.font_path, 24, bold=True)
        self.show_fleet = True
        self.command_timer = 0.0
        self.heli_time = 0.0
        self.buttons = [
            Button((324, 704, 96, 38), "9B [1]", f"远程防空，射程{HHQ9B_RANGE_KM}km", "1"),
            Button((428, 704, 96, 38), "16B [5]", f"中程防空，射程{HHQ16B_RANGE_KM}km", "5"),
            Button((532, 704, 96, 38), "YJ18 [2]", f"反舰，射程{YJ18_RANGE_KM}km", "2"),
            Button((636, 704, 96, 38), "YJ21 [3]", f"高超反舰，射程{YJ21_RANGE_KM}km", "3"),
            Button((740, 704, 96, 38), "CJ10 [4]", f"对陆巡航，射程>{CJ10_RANGE_KM}km", "4"),
            Button((844, 704, 84, 38), "搜索 [N]", "请求雷达刷新并进入下一波目标", "n"),
        ]
        self.fleet_button = Button((266, 446, 160, 32), "编队命令", "切换编队态势图，向护卫舰发送掩护命令", "f")

    def toggle_fleet(self):
        self.show_fleet = not self.show_fleet
        self.command_timer = 2.0

    def update(self, dt):
        self.command_timer = max(0.0, self.command_timer - dt)
        self.heli_time += dt

    def text(self, surface, content, pos, color=WHITE, font=None):
        surface.blit((font or self.font).render(str(content), True, color), pos)

    def panel(self, surface, rect, title=None):
        pygame.draw.rect(surface, PANEL, rect, border_radius=8)
        pygame.draw.rect(surface, PANEL_EDGE, rect, 1, border_radius=8)
        if title:
            self.text(surface, title, (rect[0] + 12, rect[1] + 8), CYAN, self.font)

    def draw_start(self, surface):
        surface.fill(BLACK)
        for r in range(80, 420, 70):
            pygame.draw.circle(surface, GREEN_DIM, (WIDTH // 2, HEIGHT // 2), r, 1)
        title = self.large.render("科技守卫家园", True, CYAN)
        sub = self.mid.render("055型南昌舰防空反导指挥模拟器", True, WHITE)
        begin = self.mid.render("按 S 键开始任务  BEGIN", True, YELLOW)
        surface.blit(title, title.get_rect(center=(WIDTH // 2, 220)))
        surface.blit(sub, sub.get_rect(center=(WIDTH // 2, 272)))
        surface.blit(begin, begin.get_rect(center=(WIDTH // 2, 390)))
        self.text(surface, "任务：保卫航母编队，抵御敌空中饱和打击", (330, 450), GREEN)
        self.text(surface, "平台：舷号101 南昌舰，112单元通用垂发系统", (330, 480), GREEN)

    def draw_game_over(self, surface, score):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        surface.blit(overlay, (0, 0))
        line1 = self.large.render("GAME OVER - 科技守卫，矢志不渝", True, RED)
        line2 = self.mid.render(f"最终得分：{score}    按 R 键重新开始", True, WHITE)
        surface.blit(line1, line1.get_rect(center=(WIDTH // 2, 330)))
        surface.blit(line2, line2.get_rect(center=(WIDTH // 2, 390)))

    def draw_top_status(self, surface, weapons, defense, battlefield, ship_health, fleet_enabled):
        self.panel(surface, (460, 20, 540, 84), None)
        status_items = [
            ("VLS", weapons.total_vls_ammo, VLS_TOTAL, CYAN),
            ("9B", weapons.hhq9b_ammo, 56, GREEN),
            ("16B", weapons.hhq16b_ammo, 12, GREEN),
            ("Y18", weapons.yj18_ammo, 16, ORANGE),
            ("Y21", weapons.yj21_ammo, 8, RED),
            ("CJ10", weapons.cj10_ammo, 12, WHITE),
            ("LZR", int(defense.laser_heat), 100, CYAN),
        ]
        x_positions = [476, 546, 616, 686, 756, 826, 896]
        for i, (label, value, maximum, color) in enumerate(status_items):
            x = x_positions[i]
            self.text(surface, label, (x, 32), color, self.small)
            pygame.draw.rect(surface, (42, 54, 58), (x, 56, 56, 10), border_radius=4)
            fill = int(56 * clamp(value / maximum, 0, 1))
            pygame.draw.rect(surface, color, (x, 56, fill, 10), border_radius=4)
            self.text(surface, str(value), (x + 36, 32), WHITE, self.small)

        pygame.draw.rect(surface, (50, 62, 66), (900, 74, 76, 8), border_radius=4)
        pygame.draw.rect(surface, GREEN if ship_health > 40 else RED, (900, 74, int(76 * ship_health / SHIP_HEALTH), 8), border_radius=4)
        self.text(surface, "HP", (960, 54), GRAY, self.small)
        self.text(surface, f"{ship_health}", (960, 32), WHITE, self.small)

        event_color = ORANGE if battlefield.active_status != "态势稳定" else GREEN
        pygame.draw.circle(surface, event_color, (476, 82), 5)
        self.text(surface, battlefield.active_status, (488, 72), event_color, self.small)
        pygame.draw.circle(surface, CYAN if fleet_enabled else GRAY, (660, 82), 5)

    def draw_radar_info(self, surface, radar, weapons):
        detected, tracked = radar.counts()
        self.text(surface, f"探测目标：{detected}  已跟踪目标：{tracked}", (24, 444), GREEN)
        self.text(surface, f"得分：{weapons.score}  成功：{weapons.kills}  失败：{weapons.failures}", (24, 468), WHITE)
        scope = RADAR_RANGE_KM if radar.network_enabled else ORGANIC_RADAR_RANGE_KM
        self.text(surface, f"态势圈：{scope}km / {px_to_km(1):.1f}km·px", (24, 492), CYAN, self.small)
        self.text(surface, weapons.last_message, (24, 512), YELLOW, self.small)
        self.fleet_button.draw(surface, self.font, pygame.mouse.get_pos())

    def draw_main_scene(self, surface, radar):
        """左下角二维态势图，额外展示直-20直升机起降动画。"""
        rect = (20, 535, 420, 145)
        self.panel(surface, rect, "二维海空态势")
        center = (230, 610)
        pygame.draw.line(surface, BLUE, (44, center[1]), (416, center[1]), 1)
        pygame.draw.line(surface, BLUE, (center[0], 556), (center[0], 664), 1)
        ship = [(center[0], center[1] - 36), (center[0] + 22, center[1] + 24), (center[0], center[1] + 42), (center[0] - 22, center[1] + 24)]
        pygame.draw.polygon(surface, SHIP_INFO_COLOR, ship)
        pygame.draw.polygon(surface, CYAN, ship, 2)
        self.text(surface, "101 南昌舰", (126, 592), WHITE, self.small)

        heli, rotor_angle, phase_name = self.helicopter_position(center)
        pygame.draw.circle(surface, YELLOW, heli, 5)
        pygame.draw.line(surface, YELLOW, (heli[0] - 10, heli[1]), (heli[0] + 10, heli[1]), 1)
        pygame.draw.line(
            surface,
            YELLOW,
            (heli[0] + math.cos(rotor_angle) * 9, heli[1] + math.sin(rotor_angle) * 9),
            (heli[0] - math.cos(rotor_angle) * 9, heli[1] - math.sin(rotor_angle) * 9),
            1,
        )
        pygame.draw.circle(surface, CYAN, (center[0] + 50, center[1] + 24), 6, 1)
        self.text(surface, f"直-20 {phase_name}", (heli[0] + 8, heli[1] - 8), YELLOW, self.small)

        for target in radar.detected_targets()[:8]:
            dx = (target.pos.x - RADAR_CENTER[0]) * 0.65
            dy = (target.pos.y - RADAR_CENTER[1]) * 0.65
            color = CYAN if target.type == TARGET_LAND else RED if target.type == TARGET_MISSILE else ORANGE
            pygame.draw.circle(surface, color, (center[0] + dx, center[1] + dy), 4)

    def helicopter_position(self, center):
        """直-20复合航迹：甲板起飞、8字巡逻、返航降落。

        比单纯绕圈更适合答辩展示“舰载直升机起降与警戒巡逻”的过程。
        """
        deck = pygame.Vector2(center[0] + 50, center[1] + 24)
        patrol_center = pygame.Vector2(center[0] + 42, center[1] - 12)
        cycle = self.heli_time % 18.0
        rotor_angle = self.heli_time * 18.0

        if cycle < 3.0:
            t = cycle / 3.0
            lift = pygame.Vector2(0, -42 * t)
            pos = deck + lift + pygame.Vector2(math.sin(t * math.pi) * 18, 0)
            phase_name = "起飞"
        elif cycle < 12.0:
            t = (cycle - 3.0) / 9.0 * math.tau
            # 8字巡逻轨迹：横向sin，纵向sin(2t)，有明显机动变化。
            pos = patrol_center + pygame.Vector2(math.sin(t) * 86, math.sin(2 * t) * 28)
            phase_name = "巡逻"
        elif cycle < 15.0:
            t = (cycle - 12.0) / 3.0
            start = patrol_center + pygame.Vector2(0, 0)
            pos = start.lerp(deck + pygame.Vector2(0, -32), t)
            pos += pygame.Vector2(math.sin(t * math.pi * 2) * 12, -math.sin(t * math.pi) * 8)
            phase_name = "返航"
        else:
            t = (cycle - 15.0) / 3.0
            pos = (deck + pygame.Vector2(0, -32)).lerp(deck, t)
            pos += pygame.Vector2(math.sin(t * math.pi) * 8, 0)
            phase_name = "降落"

        return (pos.x, pos.y), rotor_angle, phase_name

    def draw_briefing(self, surface, radar, weapons, elapsed):
        self.panel(surface, (730, 120, 270, 250), "任务")
        total = weapons.kills + weapons.failures
        rate = int(weapons.kills / total * 100) if total else 100
        detected, _ = radar.counts()
        threat = "高" if any(t.type == TARGET_MISSILE for t in radar.detected_targets()) else "中" if detected else "低"
        threat_color = RED if threat == "高" else YELLOW if threat == "中" else GREEN
        self.text(surface, "保卫航母编队", (746, 158), WHITE)
        metrics = [
            ("THR", threat, threat_color),
            ("TIME", f"{int(elapsed // 60):02d}:{int(elapsed % 60):02d}", CYAN),
            ("PK", f"{rate}%", GREEN if rate >= 70 else YELLOW),
            ("MISS", str(weapons.failures), RED if weapons.failures else GRAY),
        ]
        for i, (label, value, color) in enumerate(metrics):
            x = 746 + (i % 2) * 118
            y = 202 + (i // 2) * 54
            pygame.draw.rect(surface, (13, 28, 35), (x, y, 96, 36), border_radius=5)
            pygame.draw.rect(surface, color, (x, y, 5, 36), border_radius=3)
            self.text(surface, label, (x + 12, y + 3), GRAY, self.small)
            self.text(surface, value, (x + 46, y + 3), color, self.font)
        pygame.draw.line(surface, PANEL_EDGE, (746, 318), (976, 318), 1)
        self.text(surface, "346B / X-band", (746, 330), CYAN, self.small)
        self.text(surface, f"-{FAILURE_PENALTY}", (940, 330), RED, self.small)

    def draw_ship_specs(self, surface):
        """压缩版舰艇简介，把空间让给全景沙盘。"""
        self.panel(surface, (460, 120, 250, 76), None)
        self.text(surface, f"101 {SHIP_INFO['名称']}", (476, 136), YELLOW, self.font)
        badges = [("112", CYAN), ("9B", GREEN), ("16B", GREEN), ("H10", YELLOW), ("LZR", CYAN)]
        for i, (label, color) in enumerate(badges):
            x = 476 + i * 45
            pygame.draw.rect(surface, (12, 28, 35), (x, 166, 39, 18), border_radius=5)
            pygame.draw.circle(surface, color, (x + 9, 175), 4)
            self.text(surface, label, (x + 16, 166), WHITE, self.small)

    def draw_panorama(self, surface, radar, battlefield, weapons):
        """全景沙盘：把雷达外的信息转换成编队级战场态势。

        左侧雷达强调传感器扫描；这里强调“全局指挥”：航母、护卫舰、威胁方向、
        事件日志和空海目标分布都在同一张沙盘里展示。
        """
        rect = pygame.Rect(460, 205, 250, 475)
        self.panel(surface, rect, "沙盘")
        map_rect = pygame.Rect(476, 244, 218, 220)
        pygame.draw.rect(surface, BLACK, map_rect, border_radius=6)
        pygame.draw.rect(surface, GREEN_DIM, map_rect, 1, border_radius=6)

        center = pygame.Vector2(map_rect.center)
        land = [
            (map_rect.right - 54, map_rect.top + 12), (map_rect.right - 18, map_rect.top + 44),
            (map_rect.right - 30, map_rect.top + 96), (map_rect.right - 70, map_rect.top + 132),
            (map_rect.right - 44, map_rect.bottom - 20), (map_rect.right - 8, map_rect.bottom - 8),
            (map_rect.right - 8, map_rect.top + 8),
        ]
        pygame.draw.polygon(surface, (18, 50, 37), land)
        pygame.draw.lines(surface, GREEN_DIM, False, land, 1)
        # 航母编队基准位置。
        carrier = (center.x - 36, center.y + 22)
        pygame.draw.ellipse(surface, (55, 88, 110), (carrier[0] - 28, carrier[1] - 8, 56, 16))

        nanchang = (center.x + 18, center.y + 4)
        ship = [(nanchang[0], nanchang[1] - 15), (nanchang[0] + 10, nanchang[1] + 10), (nanchang[0], nanchang[1] + 16), (nanchang[0] - 10, nanchang[1] + 10)]
        pygame.draw.polygon(surface, CYAN, ship, 2)
        self.text(surface, "055", (nanchang[0] - 12, nanchang[1] + 18), CYAN, self.small)

        escorts = [(-74, -44), (72, -42), (-84, 54), (82, 48)]
        for offset in escorts:
            pos = center + pygame.Vector2(offset)
            color = YELLOW if battlefield.cover_timer > 0 else GREEN
            pygame.draw.circle(surface, color, pos, 4)

        # 将雷达坐标压缩投影到沙盘坐标。
        for target in radar.targets[:12]:
            rel = (target.pos - pygame.Vector2(RADAR_CENTER)) / max(1, RADAR_RADIUS)
            pos = center + pygame.Vector2(rel.x * 96, rel.y * 92)
            if not map_rect.inflate(-8, -8).collidepoint(pos):
                pos.x = clamp(pos.x, map_rect.left + 8, map_rect.right - 8)
                pos.y = clamp(pos.y, map_rect.top + 8, map_rect.bottom - 8)
            color = CYAN if target.type == TARGET_LAND else RED if target.type == TARGET_MISSILE else ORANGE if target.type == TARGET_SEA else YELLOW
            pygame.draw.circle(surface, color, pos, 5 if target.detected else 3)
            if target.detected:
                pygame.draw.line(surface, color, pos, nanchang, 1)

        if battlefield.jamming_timer > 0:
            for x in range(map_rect.left + 8, map_rect.right, 18):
                pygame.draw.line(surface, ORANGE, (x, map_rect.top + 8), (x + 12, map_rect.bottom - 8), 1)
            self.text(surface, "JAM", (490, 472), ORANGE, self.small)
        elif battlefield.low_altitude_timer > 0:
            self.text(surface, "SEA-SKIM", (490, 472), RED, self.small)
        else:
            self.text(surface, "AAW NET", (490, 472), GREEN, self.small)

        legend = [
            ("空中", YELLOW),
            ("导弹", RED),
            ("海面", ORANGE),
            ("陆上", CYAN),
        ]
        for i, (label, color) in enumerate(legend):
            x = 482 + i * 52
            pygame.draw.circle(surface, color, (x, 498), 4)
            self.text(surface, label, (x + 8, 489), WHITE, self.small)

        self.text(surface, f"态势：{battlefield.active_status}", (476, 526), YELLOW, self.small)
        self.text(surface, f"K {weapons.kills}   S {weapons.score}", (476, 548), WHITE, self.small)
        self.text(surface, "EVENT", (476, 580), CYAN, self.small)
        for i, line in enumerate(battlefield.log[:4]):
            self.text(surface, compact_log(line), (476, 604 + i * 18), WHITE if i else YELLOW, self.small)

    def draw_ciws_panel(self, surface, defense):
        self.panel(surface, (730, 390, 270, 145), "近防")
        self.text(surface, "HQ-10", (754, 424), YELLOW, self.small)
        pygame.draw.rect(surface, (50, 62, 66), (818, 430, 126, 8), border_radius=5)
        pygame.draw.rect(surface, YELLOW, (818, 430, int(126 * defense.hq10_ammo / 24), 8), border_radius=5)
        self.text(surface, str(defense.hq10_ammo), (954, 421), WHITE, self.small)

        self.text(surface, "LZR", (754, 454), CYAN, self.small)
        pygame.draw.rect(surface, (50, 62, 66), (818, 460, 126, 8), border_radius=5)
        pygame.draw.rect(surface, CYAN, (818, 460, int(126 * defense.laser_heat / 100), 8), border_radius=5)

        self.text(surface, "1130", (754, 484), ORANGE, self.small)
        bar_w = 148 if defense.active_timer > 0 else 34
        pygame.draw.rect(surface, (50, 62, 66), (818, 490, 126, 8), border_radius=5)
        pygame.draw.rect(surface, ORANGE if defense.active_timer > 0 else GREEN_DIM, (818, 490, min(bar_w, 126), 8), border_radius=5)
        pygame.draw.circle(surface, GREEN if defense.status == "待命" else ORANGE, (754, 514), 6)
        self.text(surface, compact_log(defense.last_result), (772, 504), CYAN, self.small)

        if defense.active_timer > 0:
            banner = self.mid.render("1130近防炮开火！射速11000发/分", True, YELLOW)
            surface.blit(banner, banner.get_rect(center=(WIDTH // 2, 116)))
        if defense.alert_timer > 0:
            alert = self.mid.render("近防警报：末端目标未拦截成功！", True, RED)
            surface.blit(alert, alert.get_rect(center=(WIDTH // 2, 146)))

    def draw_fleet(self, surface, radar):
        self.panel(surface, (730, 555, 270, 125), "编队")
        if not self.show_fleet:
            self.text(surface, "HIDE", (846, 612), GRAY)
            return
        origin = (850, 620)
        pygame.draw.circle(surface, CYAN, origin, 8)
        self.text(surface, "055", (836, 636), CYAN, self.small)
        escorts = [(-66, -34), (68, -30), (-78, 34), (78, 32)]
        for i, offset in enumerate(escorts):
            pos = (origin[0] + offset[0], origin[1] + offset[1])
            pygame.draw.circle(surface, GREEN, pos, 5)
        threats = radar.detected_targets()
        if threats:
            target = threats[0]
            vec = pygame.Vector2(target.pos) - pygame.Vector2(RADAR_CENTER)
            if vec.length_squared() > 0:
                vec = vec.normalize() * 48
                start = (origin[0] + vec.x, origin[1] + vec.y)
                pygame.draw.line(surface, RED, start, origin, 3)
                pygame.draw.circle(surface, RED, start, 5)
            if self.command_timer > 0 or self.show_fleet:
                self.text(surface, "COVER", (764, 566), YELLOW, self.small)

    def draw_buttons_and_tooltip(self, surface, mouse_pos):
        hover_tip = None
        for button in self.buttons:
            button.draw(surface, self.font, mouse_pos)
            if button.rect.collidepoint(mouse_pos):
                hover_tip = button.tip
        if self.fleet_button.rect.collidepoint(mouse_pos):
            hover_tip = self.fleet_button.tip
        ciws_rect = pygame.Rect(730, 390, 270, 145)
        if ciws_rect.collidepoint(mouse_pos):
            hover_tip = "近防炮在高速目标进入50像素近防圈时自动开火，80%概率拦截"
        if hover_tip:
            tip = self.small.render(hover_tip, True, BLACK)
            rect = tip.get_rect()
            rect.topleft = (mouse_pos[0] + 12, mouse_pos[1] + 16)
            rect.inflate_ip(14, 10)
            rect.clamp_ip(pygame.Rect(0, 0, WIDTH, HEIGHT))
            pygame.draw.rect(surface, YELLOW, rect, border_radius=5)
            surface.blit(tip, (rect.x + 7, rect.y + 5))

    def draw_hud(self, surface, radar, weapons, defense, battlefield, ship_health, elapsed, game_state):
        mouse_pos = pygame.mouse.get_pos()
        surface.fill(DARK)
        pygame.draw.rect(surface, BLACK, (14, 14, 432, 432), border_radius=8)
        radar.draw(surface, self.small)
        weapons.draw(surface)
        defense.draw_fire_effect(surface)
        self.draw_radar_info(surface, radar, weapons)
        self.draw_top_status(surface, weapons, defense, battlefield, clamp(ship_health, 0, 100), self.show_fleet)
        self.draw_ship_specs(surface)
        self.draw_panorama(surface, radar, battlefield, weapons)
        self.draw_briefing(surface, radar, weapons, elapsed)
        self.draw_main_scene(surface, radar)
        self.draw_ciws_panel(surface, defense)
        self.draw_fleet(surface, radar)
        self.draw_buttons_and_tooltip(surface, mouse_pos)
        if game_state == "game_over":
            self.draw_game_over(surface, weapons.score)


SHIP_INFO_COLOR = (40, 92, 124)


def find_cjk_font():
    """查找可显示中文的字体文件。

    Pygame在macOS上有时无法通过字体名称匹配到中文字体，导致中文显示为方框。
    因此这里直接按常见系统字体文件路径加载，兼顾macOS、Windows和Linux。
    """
    candidates = [
        # macOS
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        # Windows
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/msyh.ttf",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        # Linux常见中文字体
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def make_font(font_path, size, bold=False):
    """创建字体对象；找不到中文字体时才退回Pygame默认字体。"""
    if font_path:
        font = pygame.font.Font(font_path, size)
    else:
        font = pygame.font.SysFont(None, size)
    font.set_bold(bold)
    return font


def compact_log(text):
    """把事件长句压缩成适合指挥界面的短态势语。"""
    pairs = [
        ("电子干扰", "JAM干扰"),
        ("低空掠海", "SEA-SKIM"),
        ("054A协防", "054A协防"),
        ("补给", "补给"),
        ("损管", "损管+"),
        ("诱饵", "诱饵"),
        ("HQ-10", "HQ10拦截"),
        ("L-DEW", "LZR命中"),
        ("激光", "LZR"),
        ("1130", "1130开火"),
        ("对陆", "CJ10窗口"),
        ("预警机", "AEW"),
        ("高速突防", "HYPER"),
        ("陆上", "陆上节点"),
        ("未命中", "MISS"),
    ]
    for key, value in pairs:
        if key in text:
            return value
    return text[:12]
