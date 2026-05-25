"""雷达系统与目标模型。

RadarSystem 类模拟055型驱逐舰双波段雷达的展示逻辑：
1. S波段负责远距离搜索，程序中对应205像素探测半径。
2. 目标被发现后进入X波段精确跟踪，程序用黄色锁定框显示。
3. 扫描线匀速旋转，对应相控阵雷达持续刷新空海态势。
"""

import math
import random
import pygame

from config import (
    CYAN,
    GRAY,
    GREEN,
    GREEN_DIM,
    ORANGE,
    ORGANIC_RADAR_RANGE_KM,
    RADAR_CENTER,
    RADAR_RANGE_KM,
    RADAR_RADIUS,
    RADAR_SCAN_SPEED,
    RED,
    TARGET_AIRCRAFT,
    TARGET_DECOY,
    TARGET_LABELS,
    TARGET_LAND,
    TARGET_MISSILE,
    TARGET_SEA,
    WHITE,
    YELLOW,
    distance,
    km_to_px,
    kmh_to_px_per_sec,
)


class Target:
    """敌方目标。

    pos使用雷达屏幕坐标，velocity表示每秒移动像素。
    path为直线或正弦曲线，便于展示不同来袭航迹。
    """

    def __init__(self, target_id, target_type, pos, velocity, path="line", wave_amp=0):
        self.id = target_id
        self.type = target_type
        self.pos = pygame.Vector2(pos)
        self.velocity = pygame.Vector2(velocity)
        self.path = path
        self.wave_amp = wave_amp
        self.age = 0.0
        self.detected = False
        self.tracked = False
        self.selected = False
        self.alive = True
        self.breakthrough = False
        self.close_defense_checked = False
        self.hq10_checked = False
        self.escort_checked = False
        self.laser_checked = False
        self.track_noise = pygame.Vector2(0, 0)
        self.decoy_life = 0.0

    @property
    def label(self):
        return TARGET_LABELS.get(self.type, "未知目标")

    @property
    def speed_per_frame(self):
        """近防炮规则按题目要求使用 pixel/frame 口径。"""
        return self.velocity.length() / 60.0

    def update(self, dt):
        """更新目标运动。

        正弦航迹使用垂直于速度方向的偏移，模拟机动突防或掠海飞行。
        """
        self.age += dt
        if self.type == TARGET_DECOY:
            self.decoy_life -= dt
        self.pos += self.velocity * dt
        if self.path == "sine" and self.velocity.length_squared() > 0:
            direction = self.velocity.normalize()
            normal = pygame.Vector2(-direction.y, direction.x)
            wobble = math.sin(self.age * 3.2) * self.wave_amp * dt
            self.pos += normal * wobble

    def draw(self, surface, font):
        """绘制雷达目标。

        红点代表S波段发现目标，黄色框代表X波段精确跟踪。
        """
        if not self.detected:
            return
        draw_pos = self.pos + self.track_noise
        color = GRAY if self.type == TARGET_DECOY else ORANGE if self.type == TARGET_SEA else CYAN if self.type == TARGET_LAND else RED
        pygame.draw.circle(surface, color, draw_pos, 5)

        if self.tracked:
            rect = pygame.Rect(0, 0, 24, 24)
            rect.center = draw_pos
            pygame.draw.rect(surface, YELLOW, rect, 2)
            pygame.draw.line(surface, YELLOW, (rect.left - 5, rect.centery), (rect.left, rect.centery), 1)
            pygame.draw.line(surface, YELLOW, (rect.right, rect.centery), (rect.right + 5, rect.centery), 1)

        if self.selected:
            pygame.draw.circle(surface, CYAN, self.pos, 16, 2)
            tag = font.render(self.label, True, WHITE)
            surface.blit(tag, (self.pos.x + 12, self.pos.y - 14))


class RadarSystem:
    """双波段雷达系统，负责生成波次、扫描、跟踪和选择目标。"""

    def __init__(self):
        self.theta = 0.0
        self.targets = []
        self.next_id = 1
        self.wave = 0
        self.wave_cooldown = 0.0
        self.selected_target = None
        self.message = "S波段搜索中，346B雷达阵列保持360度覆盖"
        self.network_enabled = True
        self.network_quality = 1.0
        self.jamming_level = 0.0
        self.landmass = build_landmass()
        self.landmass_offset = pygame.Vector2(0, 0)
        self.dragging_landmass = False
        self.drag_offset = pygame.Vector2(0, 0)
        self.spawn_wave()

    def reset(self):
        self.__init__()

    def handle_landmass_drag(self, mouse_pos, drag_start_pos=None):
        """处理陆地轮廓拖拽功能。"""
        land_rect = self.get_landmass_bounding_rect()
        if drag_start_pos is None:
            if self.dragging_landmass:
                return True
            return land_rect.collidepoint(mouse_pos)
        else:
            if not self.dragging_landmass:
                if land_rect.collidepoint(drag_start_pos):
                    self.dragging_landmass = True
                    center = land_rect.center
                    self.drag_offset = pygame.Vector2(drag_start_pos[0] - center[0], drag_start_pos[1] - center[1])
            if self.dragging_landmass:
                new_center = (mouse_pos[0] - self.drag_offset.x, mouse_pos[1] - self.drag_offset.y)
                delta = pygame.Vector2(new_center[0] - land_rect.center[0], new_center[1] - land_rect.center[1])
                self.landmass_offset += delta
            return self.dragging_landmass

    def release_landmass_drag(self):
        """释放陆地轮廓拖拽。"""
        self.dragging_landmass = False

    def get_landmass_bounding_rect(self):
        """获取陆地轮廓的边界矩形。"""
        land_points = [(RADAR_CENTER[0] + x + self.landmass_offset.x, RADAR_CENTER[1] + y + self.landmass_offset.y) for x, y in self.landmass]
        min_x = min(p[0] for p in land_points)
        max_x = max(p[0] for p in land_points)
        min_y = min(p[1] for p in land_points)
        max_y = max(p[1] for p in land_points)
        return pygame.Rect(min_x, min_y, max_x - min_x, max_y - min_y)

    def is_point_on_land(self, pos):
        """检查点是否在陆地轮廓内。"""
        land_points = [(RADAR_CENTER[0] + x + self.landmass_offset.x, RADAR_CENTER[1] + y + self.landmass_offset.y) for x, y in self.landmass]
        return self.point_in_polygon(pos, land_points)

    def point_in_polygon(self, point, polygon):
        """射线法判断点是否在多边形内。"""
        x, y = point
        n = len(polygon)
        inside = False
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        return inside

    def get_land_point_near(self, pos, max_distance=30):
        """获取距离指定位置最近的陆地上的点。"""
        land_points = [(RADAR_CENTER[0] + x + self.landmass_offset.x, RADAR_CENTER[1] + y + self.landmass_offset.y) for x, y in self.landmass]
        best_point = None
        best_dist = max_distance
        for i in range(len(land_points)):
            p1 = land_points[i]
            p2 = land_points[(i + 1) % len(land_points)]
            closest = self.closest_point_on_segment(pos, p1, p2)
            dist = math.hypot(pos[0] - closest[0], pos[1] - closest[1])
            if dist < best_dist:
                best_dist = dist
                best_point = closest
        if best_point is None:
            for lp in land_points:
                dist = math.hypot(pos[0] - lp[0], pos[1] - lp[1])
                if dist < best_dist:
                    best_dist = dist
                    best_point = lp
        return best_point

    def closest_point_on_segment(self, point, seg_start, seg_end):
        """计算点到线段的最短距离点。"""
        px, py = point
        x1, y1 = seg_start
        x2, y2 = seg_end
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return seg_start
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        return (x1 + t * dx, y1 + t * dy)

    def spawn_wave(self):
        """按比赛要求设计三种波次。

        参考公开资料中YJ-18“亚音速巡航、末段超音速突防”的描述，
        来袭反舰导弹在雷达屏内不再全程高速飞行，而是使用较低的巡航段速度，
        让拦截窗口更接近防空指挥演示。
        """
        self.wave += 1
        count = 3 if self.wave == 1 else 4 if self.wave == 2 else 6
        for i in range(count):
            angle = random.uniform(0, math.tau)
            radius = random.uniform(RADAR_RADIUS + 25, RADAR_RADIUS + 70)
            start = pygame.Vector2(RADAR_CENTER) + pygame.Vector2(math.cos(angle), math.sin(angle)) * radius
            to_center = (pygame.Vector2(RADAR_CENTER) - start).normalize()

            if self.wave == 1:
                target_type = TARGET_AIRCRAFT
                # 亚音速飞机：约780-950km/h，按1000km雷达圈比例换算。
                speed = kmh_to_px_per_sec(random.uniform(780, 950))
                path = "sine" if i % 2 else "line"
                wave_amp = 6
            elif self.wave == 2:
                target_type = TARGET_MISSILE if i < 3 else TARGET_AIRCRAFT
                # 来袭反舰导弹巡航段约900-1150km/h，避免全程末段超高速。
                speed = kmh_to_px_per_sec(random.uniform(900, 1150)) if target_type == TARGET_MISSILE else kmh_to_px_per_sec(random.uniform(820, 980))
                path = "line"
                wave_amp = 0
            else:
                target_type = TARGET_MISSILE if i < 3 else TARGET_SEA if i < 5 else TARGET_LAND
                if target_type == TARGET_MISSILE:
                    speed = kmh_to_px_per_sec(random.uniform(980, 1350))
                    path = "sine"
                    wave_amp = 5
                elif target_type == TARGET_SEA:
                    # 敌方舰艇约18-30节，换算后在1000km沙盘上缓慢机动。
                    speed = kmh_to_px_per_sec(random.uniform(33, 56))
                    path = "sine"
                    wave_amp = 2
                else:
                    radius = random.uniform(RADAR_RADIUS * 0.72, RADAR_RADIUS * 0.95)
                    start = pygame.Vector2(RADAR_CENTER) + pygame.Vector2(math.cos(angle), math.sin(angle)) * radius
                    speed = 0
                    path = "line"
                    wave_amp = 0

            velocity = to_center * speed
            self.targets.append(Target(self.next_id, target_type, start, velocity, path, wave_amp))
            self.next_id += 1
        self.message = f"第{self.wave}波威胁接近，S波段远程搜索启动"

    def center_vector(self):
        return pygame.Vector2(RADAR_CENTER)

    def spawn_single_target(self, target_type, speed_range=(600, 900), path="line", wave_amp=0):
        """从雷达外圈生成一个单独战场事件目标。"""
        angle = random.uniform(0, math.tau)
        radius = random.uniform(RADAR_RADIUS + 60, RADAR_RADIUS + 125)
        start = self.center_vector() + pygame.Vector2(math.cos(angle), math.sin(angle)) * radius
        to_center = (self.center_vector() - start).normalize()
        speed = kmh_to_px_per_sec(random.uniform(*speed_range))
        self.targets.append(Target(self.next_id, target_type, start, to_center * speed, path, wave_amp))
        self.next_id += 1

    def spawn_decoy_cluster(self, count=3):
        """生成DRFM/箔条诱饵式假目标，干扰期间短暂存在。"""
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            radius = random.uniform(km_to_px(180), RADAR_RADIUS)
            start = self.center_vector() + pygame.Vector2(math.cos(angle), math.sin(angle)) * radius
            drift = pygame.Vector2(random.uniform(-1, 1), random.uniform(-1, 1))
            if drift.length_squared() > 0:
                drift = drift.normalize() * kmh_to_px_per_sec(random.uniform(120, 260))
            target = Target(self.next_id, TARGET_DECOY, start, drift, "sine", 4)
            target.detected = True
            target.tracked = False
            target.decoy_life = random.uniform(5.0, 9.0)
            self.targets.append(target)
            self.next_id += 1

    def spawn_fixed_land_target(self):
        """在陆地轮廓附近生成固定陆上节点，供CJ-10打击。"""
        land_edges = [(self.landmass[i], self.landmass[(i + 1) % len(self.landmass)]) for i in range(len(self.landmass))]
        base_point = random.choice(land_edges)
        edge_mid = ((base_point[0][0] + base_point[1][0]) / 2, (base_point[0][1] + base_point[1][1]) / 2)
        land_edge_pos = pygame.Vector2(RADAR_CENTER) + pygame.Vector2(edge_mid) + self.landmass_offset
        jitter = pygame.Vector2(random.uniform(-12, 12), random.uniform(-10, 10))
        pos = land_edge_pos + jitter
        target = Target(self.next_id, TARGET_LAND, pos, pygame.Vector2(0, 0), "line", 0)
        target.detected = True
        target.tracked = True
        self.targets.append(target)
        self.next_id += 1

    def update(self, dt):
        """更新扫描线和目标状态。

        目标进入雷达半径后视为S波段发现，随后自动进入X波段精确跟踪。
        """
        self.theta = (self.theta + RADAR_SCAN_SPEED * dt) % math.tau
        alive_targets = []
        network_range = RADAR_RADIUS if self.network_enabled else km_to_px(ORGANIC_RADAR_RANGE_KM)
        effective_range = network_range * (1.0 - 0.35 * self.jamming_level)
        for target in self.targets:
            target.update(dt)
            dist = distance(target.pos, RADAR_CENTER)
            if target.type == TARGET_DECOY and target.decoy_life <= 0:
                continue
            target.detected = dist <= effective_range or target.type == TARGET_DECOY
            if target.detected:
                track_probability = max(0.25, self.network_quality - 0.45 * self.jamming_level)
                target.tracked = target.type != TARGET_DECOY and random.random() < track_probability
                noise = 12 * self.jamming_level
                target.track_noise = pygame.Vector2(random.uniform(-noise, noise), random.uniform(-noise, noise))
            else:
                target.tracked = False
                target.track_noise = pygame.Vector2(0, 0)
            if dist < km_to_px(2):
                target.breakthrough = True
            if target.alive and not target.breakthrough and dist < RADAR_RADIUS + 160:
                alive_targets.append(target)
            elif target.breakthrough:
                alive_targets.append(target)

        self.targets = alive_targets
        if self.selected_target and (not self.selected_target.alive or self.selected_target not in self.targets):
            self.selected_target = None

        if not self.targets:
            self.wave_cooldown += dt
            if self.wave_cooldown > 2.5 and self.wave < 3:
                self.wave_cooldown = 0
                self.spawn_wave()

    def pick_target(self, mouse_pos):
        """鼠标点击雷达目标，选择后可按1/2键发射武器。"""
        self.selected_target = None
        for target in self.targets:
            target.selected = False
            if target.detected and distance(target.pos, mouse_pos) <= 14:
                self.selected_target = target
        if self.selected_target:
            self.selected_target.selected = True
            self.message = f"X波段精确跟踪：{self.selected_target.label} #{self.selected_target.id}"
        return self.selected_target

    def remove_target(self, target):
        if target in self.targets:
            target.alive = False
            self.targets.remove(target)
        if self.selected_target == target:
            self.selected_target = None

    def counts(self):
        detected = sum(1 for t in self.targets if t.detected)
        tracked = sum(1 for t in self.targets if t.tracked)
        return detected, tracked

    def detected_targets(self):
        return [t for t in self.targets if t.detected]

    def draw(self, surface, font):
        """绘制圆形雷达屏、距离圈、扫描线、目标点和锁定框。"""
        old_clip = surface.get_clip()
        surface.set_clip(pygame.Rect(14, 14, 432, 432))
        self.draw_landmass(surface)
        pygame.draw.circle(surface, GREEN_DIM, RADAR_CENTER, RADAR_RADIUS, 2)
        pygame.draw.circle(surface, GREEN_DIM, RADAR_CENTER, int(RADAR_RADIUS * 0.66), 1)
        pygame.draw.circle(surface, GREEN_DIM, RADAR_CENTER, int(RADAR_RADIUS * 0.33), 1)
        pygame.draw.line(surface, GREEN_DIM, (RADAR_CENTER[0] - RADAR_RADIUS, RADAR_CENTER[1]), (RADAR_CENTER[0] + RADAR_RADIUS, RADAR_CENTER[1]), 1)
        pygame.draw.line(surface, GREEN_DIM, (RADAR_CENTER[0], RADAR_CENTER[1] - RADAR_RADIUS), (RADAR_CENTER[0], RADAR_CENTER[1] + RADAR_RADIUS), 1)

        end = (
            RADAR_CENTER[0] + math.cos(self.theta) * RADAR_RADIUS,
            RADAR_CENTER[1] + math.sin(self.theta) * RADAR_RADIUS,
        )
        pygame.draw.line(surface, GREEN, RADAR_CENTER, end, 3)

        # 南昌舰图标：中心蓝色舰形符号，代表雷达阵面所在平台。
        cx, cy = RADAR_CENTER
        ship = [(cx, cy - 16), (cx + 14, cy + 4), (cx, cy + 16), (cx - 14, cy + 4)]
        pygame.draw.polygon(surface, CYAN, ship, 2)
        pygame.draw.circle(surface, WHITE, RADAR_CENTER, 3)

        for target in self.targets:
            target.draw(surface, font)
        surface.set_clip(old_clip)

    def draw_landmass(self, surface):
        """绘制陆地轮廓，让陆上目标/CJ-10任务有地理语境。"""
        land_points = [(RADAR_CENTER[0] + x + self.landmass_offset.x, RADAR_CENTER[1] + y + self.landmass_offset.y) for x, y in self.landmass]
        pygame.draw.polygon(surface, (17, 48, 37), land_points)
        pygame.draw.lines(surface, GREEN_DIM, False, land_points, 2)
        for point in land_points[::2]:
            pygame.draw.circle(surface, (35, 86, 55), point, 2)


def build_landmass():
    """生成雷达右侧沿海陆地的轮廓点。"""
    return [
        (78, -205), (128, -190), (178, -162), (208, -118), (222, -72),
        (214, -30), (190, 8), (162, 38), (132, 70), (116, 108),
        (146, 160), (222, 216), (250, 226), (250, -226),
    ]
