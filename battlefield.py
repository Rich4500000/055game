"""全景沙盘与随机战场事件。

BattlefieldManager 负责让战场不再只是“发现目标-点击-发射”的单循环。
它会定时触发电子干扰、低空突防、编队协防和弹药补给等情景，并把效果应用到
雷达、武器和舰艇状态上。
"""

import random

from config import (
    CJ10_AMMO,
    HHQ16B_AMMO,
    HHQ9B_AMMO,
    RADAR_CENTER,
    YJ18_AMMO,
    YJ21_AMMO,
    TARGET_AIRCRAFT,
    TARGET_LAND,
    TARGET_MISSILE,
    TARGET_SEA,
    distance,
)


class BattlefieldManager:
    """战场事件管理器。"""

    def __init__(self):
        self.event_timer = 7.0
        self.jamming_timer = 0.0
        self.cover_timer = 0.0
        self.low_altitude_timer = 0.0
        self.aew_gap_timer = 0.0
        self.escort_cooldown = 4.0
        self.strike_window_timer = 0.0
        self.aew_sweep_timer = 0.0
        self.log = ["航母/预警机数据链接入：1000km态势圈"]

    def reset(self):
        self.__init__()

    def push_log(self, text):
        self.log.insert(0, text)
        self.log = self.log[:5]

    @property
    def active_status(self):
        if self.jamming_timer > 0:
            return "ECM压制"
        if self.aew_gap_timer > 0:
            return "本舰雷达"
        if self.strike_window_timer > 0:
            return "对陆窗口"
        if self.aew_sweep_timer > 0:
            return "预警补盲"
        if self.low_altitude_timer > 0:
            return "低空突防"
        if self.cover_timer > 0:
            return "编队协防"
        return "态势稳定"

    def update(self, dt, radar, weapons):
        """更新战场事件，并返回舰艇生命值修复量。"""
        health_delta = 0
        self.jamming_timer = max(0.0, self.jamming_timer - dt)
        self.cover_timer = max(0.0, self.cover_timer - dt)
        self.low_altitude_timer = max(0.0, self.low_altitude_timer - dt)
        self.aew_gap_timer = max(0.0, self.aew_gap_timer - dt)
        self.strike_window_timer = max(0.0, self.strike_window_timer - dt)
        self.aew_sweep_timer = max(0.0, self.aew_sweep_timer - dt)
        self.escort_cooldown = max(0.0, self.escort_cooldown - dt)

        self.apply_network_state(radar)
        self.apply_continuous_effects(radar)
        self.apply_escort_defense(radar, weapons)

        self.event_timer -= dt
        if self.event_timer <= 0:
            self.event_timer = random.uniform(9.0, 15.0)
            health_delta += self.trigger_event(radar, weapons)
        return health_delta

    def apply_network_state(self, radar):
        """航母/预警机数据链决定是否能维持1000km态势圈。"""
        network_available = self.aew_gap_timer <= 0
        if self.jamming_timer > 0:
            radar.network_enabled = network_available
            radar.network_quality = 0.48
            radar.jamming_level = 0.85
            return
        radar.network_enabled = network_available
        radar.network_quality = 1.0 if radar.network_enabled else 0.72
        radar.jamming_level = 0.0

    def apply_escort_defense(self, radar, weapons):
        """附近护卫舰协助055处理来袭导弹。

        编队协防不需要玩家操作：当已探测反舰导弹进入中近程威胁圈，
        054A等伴随舰艇会周期性尝试拦截，体现编队作战。
        """
        if self.escort_cooldown > 0:
            return
        missiles = [
            t for t in radar.detected_targets()
            if t.type == TARGET_MISSILE and not t.escort_checked and distance(t.pos, RADAR_CENTER) < 155
        ]
        if not missiles:
            return
        target = min(missiles, key=lambda t: distance(t.pos, RADAR_CENTER))
        target.escort_checked = True
        self.escort_cooldown = 5.5
        self.cover_timer = 1.8
        if random.random() < 0.68:
            weapons.register_kill(target, radar)
            weapons.last_message = "054A协防拦截"
            self.push_log("054A协防：来袭导弹被处理")
        else:
            weapons.last_message = "054A协防未命中"
            self.push_log("054A补射未命中，055继续接战")

    def apply_continuous_effects(self, radar):
        """电子干扰期间，制造假目标并让目标跟踪产生角度/距离误差。"""
        if self.jamming_timer <= 0:
            return
        if random.random() < 0.035:
            radar.spawn_decoy_cluster(random.randint(1, 2))
        for target in radar.detected_targets():
            if random.random() < 0.08:
                target.tracked = False
            elif target.detected and random.random() < 0.04:
                target.tracked = True

    def trigger_event(self, radar, weapons):
        """随机选择并执行一个战场情景。"""
        choices = [
            "jamming", "sea_skimmer", "fleet_cover", "replenish", "damage_control",
            "decoy", "aew_gap", "land_strike", "aew_sweep", "hypersonic_raid"
        ]
        event = random.choice(choices)

        if event == "jamming":
            self.jamming_timer = 8.0
            radar.spawn_decoy_cluster(3)
            radar.message = "ECM压制：数据链降质、假目标出现"
            self.push_log("ECM压制：数据链降质/假目标")
            return 0

        if event == "aew_gap":
            self.aew_gap_timer = 8.0
            # 这里用短暂离位模拟预警机转场/遮蔽，结束后自动恢复1000km态势圈。
            self.push_log("预警机转场：055切回本舰雷达")
            radar.message = "预警机链路短暂离位，本舰雷达独立搜索"
            return 0

        if event == "sea_skimmer":
            radar.spawn_single_target(TARGET_MISSILE, speed_range=(850, 1050), path="sine", wave_amp=3)
            self.low_altitude_timer = 5.0
            radar.message = "低空掠海目标突防，注意近防炮末端拦截"
            self.push_log("低空掠海反舰导弹从外圈切入")
            return 0

        if event == "hypersonic_raid":
            radar.spawn_single_target(TARGET_MISSILE, speed_range=(3600, 4800), path="sine", wave_amp=2)
            self.low_altitude_timer = 4.0
            radar.message = "高速突防目标出现，优先HHQ-9B/16B接战"
            self.push_log("高速突防：来袭弹进入外层防空圈")
            return 0

        if event == "land_strike":
            self.strike_window_timer = 10.0
            for _ in range(2):
                radar.spawn_fixed_land_target()
            radar.message = "对陆打击窗口：选择陆上目标发射CJ-10"
            self.push_log("CJ-10窗口：陆上节点暴露")
            return 0

        if event == "aew_sweep":
            self.aew_sweep_timer = 6.0
            radar.network_enabled = True
            radar.network_quality = 1.0
            for target in radar.targets:
                target.detected = True
                if target.type != "decoy_target":
                    target.tracked = True
            radar.message = "预警机补盲扫描：目标短时全显"
            self.push_log("预警机补盲：目标全显")
            return 0

        if event == "fleet_cover":
            self.cover_timer = 4.0
            target = self.pick_cover_target(radar)
            if target:
                weapons.register_kill(target, radar)
                weapons.last_message = "编队协防：护卫舰协同拦截一个威胁"
                self.push_log("054A护卫舰执行协防拦截")
            else:
                self.push_log("编队进入协防阵位，等待威胁进入射界")
            return 0

        if event == "replenish":
            before = (weapons.hhq9b_ammo, weapons.hhq16b_ammo, weapons.yj18_ammo, weapons.yj21_ammo, weapons.cj10_ammo)
            weapons.hhq9b_ammo = min(HHQ9B_AMMO, weapons.hhq9b_ammo + 4)
            weapons.hhq16b_ammo = min(HHQ16B_AMMO, weapons.hhq16b_ammo + 2)
            weapons.yj18_ammo = min(YJ18_AMMO, weapons.yj18_ammo + 2)
            weapons.yj21_ammo = min(YJ21_AMMO, weapons.yj21_ammo + 1)
            weapons.cj10_ammo = min(CJ10_AMMO, weapons.cj10_ammo + 1)
            if before != (weapons.hhq9b_ammo, weapons.hhq16b_ammo, weapons.yj18_ammo, weapons.yj21_ammo, weapons.cj10_ammo):
                self.push_log("补给窗口开启：垂发弹药少量恢复")
                weapons.last_message = "补给：9B+4 16B+2 Y18+2"
            else:
                self.push_log("补给窗口开启，但当前弹药已满")
            return 0

        if event == "damage_control":
            self.push_log("损管小组完成抢修，舰艇生命值恢复")
            weapons.last_message = "损管抢修：舰艇生命值 +10"
            return 10

        # 诱饵云会增加雷达判读压力，但速度较慢，主要用于丰富沙盘态势。
        for _ in range(2):
            radar.spawn_single_target(TARGET_AIRCRAFT, speed_range=(520, 680), path="sine", wave_amp=8)
        radar.message = "雷达发现诱饵/伴随目标，注意甄别优先级"
        self.push_log("敌方释放诱饵目标，雷达画面目标增多")
        return 0

    def pick_cover_target(self, radar):
        detected = radar.detected_targets()
        if not detected:
            return None
        missiles = [t for t in detected if t.type == TARGET_MISSILE]
        candidates = missiles or detected
        return min(candidates, key=lambda t: t.pos.distance_to(radar.center_vector()))
