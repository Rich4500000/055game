"""1130近防炮自动末端拦截系统。"""

import random
import pygame

from config import (
    CYAN,
    GREEN,
    HQ10_CELLS,
    LASER_HEAT_MAX,
    LASER_RANGE,
    ORANGE,
    RADAR_CENTER,
    RED,
    TARGET_AIRCRAFT,
    TARGET_MISSILE,
    YELLOW,
    distance,
    km_to_px,
)


class CloseInDefenseSystem:
    """模拟1130近防炮末端防御。

    先由HQ-10近程防空导弹补射，再由激光防空模块处理低成本小目标，
    最后由1130近防炮在末端圈开火，形成多层防御展示。
    """

    def __init__(self, sound=None):
        self.active_timer = 0.0
        self.hq10_timer = 0.0
        self.laser_timer = 0.0
        self.laser_heat = 0.0
        self.laser_beam = None
        self.alert_timer = 0.0
        self.status = "待命"
        self.hq10_ammo = HQ10_CELLS
        self.sound = sound or {}
        self.last_result = "分层防御待命"

    def reset(self):
        sound = self.sound
        self.__init__(sound)

    def update(self, dt, radar, weapons):
        self.active_timer = max(0.0, self.active_timer - dt)
        self.hq10_timer = max(0.0, self.hq10_timer - dt)
        self.laser_timer = max(0.0, self.laser_timer - dt)
        self.laser_heat = max(0.0, self.laser_heat - 18 * dt)
        if self.laser_timer <= 0:
            self.laser_beam = None
        self.alert_timer = max(0.0, self.alert_timer - dt)
        self.status = "CIWS" if self.active_timer > 0 else "LASER" if self.laser_timer > 0 else "HQ-10" if self.hq10_timer > 0 else "待命"

        for target in list(radar.targets):
            if self.try_laser_intercept(target, radar, weapons):
                continue

            if target.type == TARGET_MISSILE and not target.hq10_checked:
                hq10_zone = distance(target.pos, RADAR_CENTER) < km_to_px(9)
                if hq10_zone and self.hq10_ammo > 0:
                    target.hq10_checked = True
                    self.hq10_ammo -= 1
                    self.hq10_timer = 0.9
                    if "launch" in self.sound:
                        self.sound["launch"].play()
                    if random.random() < 0.76:
                        self.last_result = "HQ-10近程弹拦截来袭导弹"
                        weapons.register_kill(target, radar)
                        continue
                    self.last_result = "HQ-10未命中，转入1130末端防御"

            if target.close_defense_checked:
                continue
            close_enough = distance(target.pos, RADAR_CENTER) < km_to_px(4)
            # 使用1000km比例尺后，导弹屏幕速度显著降低；0.04px/frame约等于700km/h量级。
            fast_enough = target.speed_per_frame > 0.04
            if close_enough and fast_enough:
                target.close_defense_checked = True
                self.active_timer = 1.2
                if "ciws" in self.sound:
                    self.sound["ciws"].play()
                if random.random() < 0.9:
                    self.last_result = "1130近防炮命中，末端目标被摧毁"
                    weapons.register_kill(target, radar)
                else:
                    self.alert_timer = 1.4
                    self.last_result = "警报：近防炮未能拦截，目标继续突防"

    def try_laser_intercept(self, target, radar, weapons):
        """激光防空演示模块。

        公开资料没有确认055现役激光武器参数，因此这里用“定向能技术演示”的
        游戏化规则：无弹药消耗、受热量限制，优先处理无人机/敌机和低空导弹。
        """
        if target.laser_checked or not target.detected or not target.tracked:
            return False
        if self.laser_heat > LASER_HEAT_MAX * 0.82:
            return False
        if distance(target.pos, RADAR_CENTER) > LASER_RANGE:
            return False
        valid_target = target.type == TARGET_AIRCRAFT or (target.type == TARGET_MISSILE and target.speed_per_frame <= 2.25)
        if not valid_target:
            return False

        target.laser_checked = True
        self.laser_timer = 0.45
        self.laser_heat = min(LASER_HEAT_MAX, self.laser_heat + (32 if target.type == TARGET_MISSILE else 22))
        self.laser_beam = tuple(target.pos)
        if random.random() < (0.82 if target.type == TARGET_AIRCRAFT else 0.58):
            self.last_result = "L-DEW激光防空命中"
            weapons.register_kill(target, radar)
        else:
            self.last_result = "L-DEW照射未毁伤"
        return True

    def draw_fire_effect(self, surface):
        """黄红色锥形火焰表示1130近防炮高速弹幕。"""
        if self.laser_timer > 0 and self.laser_beam:
            pygame.draw.line(surface, CYAN, RADAR_CENTER, self.laser_beam, 3)
            pygame.draw.circle(surface, CYAN, self.laser_beam, 10, 1)
        if self.active_timer <= 0:
            if self.hq10_timer > 0:
                for angle in (-0.2, 0.0, 0.2):
                    end = (RADAR_CENTER[0] + 34, RADAR_CENTER[1] + angle * 42)
                    pygame.draw.line(surface, GREEN, RADAR_CENTER, end, 2)
            return
        intensity = int(24 + self.active_timer * 22)
        for spread in range(-2, 3):
            end = (RADAR_CENTER[0] + 25 + intensity, RADAR_CENTER[1] + spread * 12)
            points = [RADAR_CENTER, (RADAR_CENTER[0] + 18, RADAR_CENTER[1] - 14), end, (RADAR_CENTER[0] + 18, RADAR_CENTER[1] + 14)]
            pygame.draw.polygon(surface, random.choice([YELLOW, ORANGE, RED]), points, 1)
