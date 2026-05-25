"""武器控制系统。

WeaponSystem 管理HHQ-9B、HHQ-16B、YJ-18、YJ-21、CJ-10发射、导弹追踪、命中判定与爆炸粒子。
本模拟将复杂制导过程抽象为“从舰位发射、持续指向目标、接近后引爆”。
"""

import math
import random
import pygame

from config import (
    CYAN,
    GREEN,
    CJ10_AMMO,
    CJ10_RANGE_KM,
    HHQ9B_AMMO,
    HHQ9B_RANGE_KM,
    HHQ16B_AMMO,
    HHQ16B_RANGE_KM,
    ORANGE,
    RADAR_CENTER,
    RED,
    SCORE_AIRCRAFT,
    SCORE_MISSILE,
    TARGET_AIRCRAFT,
    TARGET_LAND,
    TARGET_MISSILE,
    TARGET_SEA,
    WHITE,
    YELLOW,
    YJ18_AMMO,
    YJ18_RANGE_KM,
    YJ21_AMMO,
    YJ21_RANGE_KM,
    distance,
    kmh_to_px_per_sec,
    px_to_km,
)


class Missile:
    """拦截弹/反舰弹动画对象。"""

    def __init__(self, target, missile_type):
        self.target = target
        self.type = missile_type
        self.pos = pygame.Vector2(RADAR_CENTER)
        speed_kmh = {
            "HHQ-9B": 4700,
            "HHQ-16B": 3600,
            "YJ-18": 3200,
            "YJ-21": 9000,
            "CJ-10": 880,
        }.get(missile_type, 1200)
        self.speed = kmh_to_px_per_sec(speed_kmh)
        self.alive = True
        self.trail = []

    def update(self, dt):
        """导弹持续追踪当前目标。

        真实舰空导弹依靠舰载雷达、数据链和弹载导引头协同制导；这里用向量逼近展示其原理。
        """
        if not self.target or not self.target.alive:
            self.alive = False
            return False
        direction = self.target.pos - self.pos
        if direction.length() < 8:
            self.alive = False
            return True
        self.pos += direction.normalize() * self.speed * dt
        self.trail.append(tuple(self.pos))
        self.trail = self.trail[-14:]
        return False

    def draw(self, surface):
        for i, point in enumerate(self.trail):
            alpha_color = (180 + i * 5, 210 + i * 3, 255)
            pygame.draw.circle(surface, alpha_color, point, max(1, i // 4))
        pygame.draw.circle(surface, WHITE, self.pos, 4)
        color = CYAN if self.type == "HHQ-9B" else GREEN if self.type == "HHQ-16B" else RED if self.type == "YJ-21" else ORANGE if self.type == "CJ-10" else YELLOW
        pygame.draw.circle(surface, color, self.pos, 7, 1)


class ExplosionParticle:
    """命中爆炸粒子，橙红色扩散后逐渐消失。"""

    def __init__(self, pos):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(35, 150)
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(math.cos(angle), math.sin(angle)) * speed
        self.life = random.uniform(0.35, 0.8)
        self.max_life = self.life
        self.radius = random.randint(3, 7)
        self.color = random.choice([ORANGE, RED, YELLOW])

    def update(self, dt):
        self.life -= dt
        self.pos += self.vel * dt
        return self.life > 0

    def draw(self, surface):
        ratio = max(0.0, self.life / self.max_life)
        radius = max(1, int(self.radius * ratio))
        pygame.draw.circle(surface, self.color, self.pos, radius)


class WeaponSystem:
    """舰载武器系统，包含弹药、计分和音效触发。"""

    def __init__(self, sound=None):
        self.hhq9b_ammo = HHQ9B_AMMO
        self.hhq16b_ammo = HHQ16B_AMMO
        self.yj18_ammo = YJ18_AMMO
        self.yj21_ammo = YJ21_AMMO
        self.cj10_ammo = CJ10_AMMO
        self.missiles = []
        self.explosions = []
        self.kills = 0
        self.failures = 0
        self.score = 0
        self.sound = sound or {}
        self.last_message = "1远防 5中防 2反舰 3高超 4对陆"

    def reset(self):
        sound = self.sound
        self.__init__(sound)

    @property
    def total_vls_ammo(self):
        return self.hhq9b_ammo + self.hhq16b_ammo + self.yj18_ammo + self.yj21_ammo + self.cj10_ammo

    def launch(self, target, missile_type):
        """根据目标类型和快捷键发射武器。

        1键：海红旗-9B远程防空导弹，适合敌机/来袭导弹。
        2键：鹰击-18反舰导弹，适合海面目标。
        3键：鹰击-21高超音速导弹，适合高价值海面目标。
        4键：长剑-10巡航导弹，适合陆上目标。
        """
        if not target:
            self.last_message = "未选择目标：请先点击雷达目标"
            return False
        if not self.in_range(target, missile_type):
            self.last_message = f"{missile_type}射程不足 {int(px_to_km(distance(target.pos, RADAR_CENTER)))}km"
            return False
        if missile_type == "HHQ-9B":
            if self.hhq9b_ammo <= 0:
                self.last_message = "HHQ-9B弹药不足"
                return False
            if target.type not in (TARGET_AIRCRAFT, TARGET_MISSILE):
                self.last_message = "HHQ-9B仅接战空中目标"
                return False
            self.hhq9b_ammo -= 1
        elif missile_type == "HHQ-16B":
            if self.hhq16b_ammo <= 0:
                self.last_message = "HHQ-16B弹药不足"
                return False
            if target.type not in (TARGET_AIRCRAFT, TARGET_MISSILE):
                self.last_message = "HHQ-16B仅接战空中目标"
                return False
            self.hhq16b_ammo -= 1
        elif missile_type == "YJ-18":
            if self.yj18_ammo <= 0:
                self.last_message = "YJ-18弹药不足"
                return False
            if target.type != TARGET_SEA:
                self.last_message = "YJ-18用于反舰，请选择海面目标"
                return False
            self.yj18_ammo -= 1
        elif missile_type == "YJ-21":
            if self.yj21_ammo <= 0:
                self.last_message = "YJ-21弹药不足"
                return False
            if target.type != TARGET_SEA:
                self.last_message = "YJ-21用于高价值海面目标"
                return False
            self.yj21_ammo -= 1
        elif missile_type == "CJ-10":
            if self.cj10_ammo <= 0:
                self.last_message = "CJ-10弹药不足"
                return False
            if target.type != TARGET_LAND:
                self.last_message = "CJ-10用于对陆目标"
                return False
            self.cj10_ammo -= 1
        else:
            return False

        self.missiles.append(Missile(target, missile_type))
        self.last_message = f"{missile_type}已发射，目标 #{target.id}"
        if "launch" in self.sound:
            self.sound["launch"].play()
        return True

    def in_range(self, target, missile_type):
        range_km = {
            "HHQ-9B": HHQ9B_RANGE_KM,
            "HHQ-16B": HHQ16B_RANGE_KM,
            "YJ-18": YJ18_RANGE_KM,
            "YJ-21": YJ21_RANGE_KM,
            "CJ-10": CJ10_RANGE_KM,
        }.get(missile_type, 0)
        return px_to_km(distance(target.pos, RADAR_CENTER)) <= range_km

    def add_explosion(self, pos, count=34):
        """生成爆炸粒子云，对应命中目标后的毁伤效果。"""
        for _ in range(count):
            self.explosions.append(ExplosionParticle(pos))
        if "explode" in self.sound:
            self.sound["explode"].play()

    def register_kill(self, target, radar):
        self.kills += 1
        self.score += SCORE_MISSILE if target.type == TARGET_MISSILE else SCORE_AIRCRAFT
        self.add_explosion(target.pos)
        radar.remove_target(target)

    def register_failure(self):
        self.failures += 1
        self.score -= 5
        self.last_message = "警报：目标突破防御圈，舰艇受损"

    def update(self, dt, radar):
        for missile in list(self.missiles):
            hit = missile.update(dt)
            if hit and missile.target in radar.targets:
                self.register_kill(missile.target, radar)
            if hit or not missile.alive or distance(missile.pos, RADAR_CENTER) > 330:
                if missile in self.missiles:
                    self.missiles.remove(missile)

        self.explosions = [p for p in self.explosions if p.update(dt)]

    def draw(self, surface):
        for missile in self.missiles:
            missile.draw(surface)
        for particle in self.explosions:
            particle.draw(surface)
