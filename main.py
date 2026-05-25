"""科技守卫家园 - 055型南昌舰指挥模拟器。

运行方式：
    python main.py

操作：
    S 开始任务；鼠标点击雷达目标；1 HHQ-9B；5 HHQ-16B；2 YJ-18；3 YJ-21；4 CJ-10；
    F 或“编队命令”按钮切换编队图；N 搜索下一波目标；R 重新开始。
"""

import math
import os
import sys

import pygame

from config import (
    FAILURE_PENALTY,
    FPS,
    HEIGHT,
    MAX_FAILURES,
    RADAR_CENTER,
    SHIP_HEALTH,
    TITLE,
    WIDTH,
    distance,
)
from defense import CloseInDefenseSystem
from battlefield import BattlefieldManager
from radar import RadarSystem
from ui import DefenseUI
from weapons import WeaponSystem


def make_tone(frequency=440, duration=0.12, volume=0.3):
    """用程序生成短音效，避免外部音频文件依赖。

    这满足题目“pygame.mixer音效”的要求，同时让PyInstaller打包更简单。
    """
    try:
        import numpy as np

        sample_rate = 44100
        samples = int(sample_rate * duration)
        t = np.linspace(0, duration, samples, False)
        wave = np.sin(frequency * math.tau * t) * volume
        envelope = np.linspace(1.0, 0.0, samples)
        audio = (wave * envelope * 32767).astype(np.int16)
        stereo = np.column_stack([audio, audio])
        return pygame.sndarray.make_sound(stereo)
    except Exception:
        return None


def load_sounds():
    """初始化混音器并返回音效字典。"""
    sounds = {}
    try:
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        launch = make_tone(760, 0.12, 0.25)
        explode = make_tone(110, 0.22, 0.35)
        ciws = make_tone(1320, 0.18, 0.18)
        if launch:
            sounds["launch"] = launch
        if explode:
            sounds["explode"] = explode
        if ciws:
            sounds["ciws"] = ciws
    except pygame.error:
        # 某些答辩电脑没有可用音频设备，游戏仍可正常运行。
        pass
    return sounds


class Game:
    """主游戏对象，组织雷达、武器、近防炮和UI模块。"""

    def __init__(self):
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()
        self.sounds = load_sounds()
        self.ui = DefenseUI()
        self.radar = RadarSystem()
        self.weapons = WeaponSystem(self.sounds)
        self.defense = CloseInDefenseSystem(self.sounds)
        self.battlefield = BattlefieldManager()
        self.state = "start"
        self.elapsed = 0.0
        self.ship_health = SHIP_HEALTH
        self.running = True

    def reset(self):
        self.radar.reset()
        self.weapons.reset()
        self.defense.reset()
        self.battlefield.reset()
        self.elapsed = 0.0
        self.ship_health = SHIP_HEALTH
        self.state = "playing"

    def handle_key(self, key):
        if self.state == "start" and key == pygame.K_s:
            self.state = "playing"
            return
        if key == pygame.K_r:
            self.reset()
            return
        if self.state != "playing":
            return

        if key == pygame.K_1:
            self.weapons.launch(self.radar.selected_target, "HHQ-9B")
        elif key == pygame.K_2:
            self.weapons.launch(self.radar.selected_target, "YJ-18")
        elif key == pygame.K_3:
            self.weapons.launch(self.radar.selected_target, "YJ-21")
        elif key == pygame.K_4:
            self.weapons.launch(self.radar.selected_target, "CJ-10")
        elif key == pygame.K_5:
            self.weapons.launch(self.radar.selected_target, "HHQ-16B")
        elif key == pygame.K_f:
            self.ui.toggle_fleet()
        elif key == pygame.K_n:
            if not self.radar.targets:
                self.radar.spawn_wave()
            else:
                self.radar.message = "雷达仍在跟踪当前威胁，暂不切换波次"

    def handle_mouse(self, pos):
        if self.state != "playing":
            return
        if self.ui.fleet_button.rect.collidepoint(pos):
            self.ui.toggle_fleet()
            return
        for button in self.ui.buttons:
            if button.rect.collidepoint(pos):
                if button.hotkey == "1":
                    self.weapons.launch(self.radar.selected_target, "HHQ-9B")
                elif button.hotkey == "2":
                    self.weapons.launch(self.radar.selected_target, "YJ-18")
                elif button.hotkey == "3":
                    self.weapons.launch(self.radar.selected_target, "YJ-21")
                elif button.hotkey == "4":
                    self.weapons.launch(self.radar.selected_target, "CJ-10")
                elif button.hotkey == "5":
                    self.weapons.launch(self.radar.selected_target, "HHQ-16B")
                elif button.hotkey == "n" and not self.radar.targets:
                    self.radar.spawn_wave()
                return
        self.radar.pick_target(pos)

    def handle_mouse_drag(self, pos, drag_start):
        """处理鼠标拖拽事件，用于移动雷达上的陆地轮廓。"""
        if self.state != "playing":
            return
        self.radar.handle_landmass_drag(pos, drag_start)

    def process_events(self):
        drag_start = None
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                self.handle_key(event.key)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.handle_mouse(event.pos)
                drag_start = event.pos
            elif event.type == pygame.MOUSEMOTION:
                if drag_start is not None:
                    self.handle_mouse_drag(event.pos, drag_start)
            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                if self.radar.dragging_landmass:
                    self.radar.release_landmass_drag()
                drag_start = None

    def apply_breakthroughs(self):
        """处理突破防御圈的目标，扣分、扣生命并触发游戏失败条件。"""
        for target in list(self.radar.targets):
            if target.breakthrough:
                self.weapons.register_failure()
                self.ship_health -= 25
                self.radar.remove_target(target)
                self.weapons.score -= max(0, FAILURE_PENALTY - 5)

        if self.weapons.failures >= MAX_FAILURES or self.ship_health <= 0:
            self.state = "game_over"

    def update(self, dt):
        self.ui.update(dt)
        if self.state != "playing":
            return
        self.elapsed += dt
        self.ship_health = min(SHIP_HEALTH, self.ship_health + self.battlefield.update(dt, self.radar, self.weapons))
        self.radar.update(dt)
        self.defense.update(dt, self.radar, self.weapons)
        self.weapons.update(dt, self.radar)
        self.apply_breakthroughs()

    def draw(self):
        if self.state == "start":
            self.ui.draw_start(self.screen)
        else:
            self.ui.draw_hud(
                self.screen,
                self.radar,
                self.weapons,
                self.defense,
                self.battlefield,
                self.ship_health,
                self.elapsed,
                self.state,
            )
        pygame.display.flip()

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.process_events()
            self.update(dt)
            self.draw()
        pygame.quit()


def main():
    Game().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
