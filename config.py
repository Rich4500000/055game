"""055型南昌舰指挥模拟器 - 全局配置。

本文件集中保存窗口、颜色、真实舰艇参数和游戏数值，便于答辩时说明：
程序中的“装备参数”和“游戏规则参数”是分离管理的。
"""

import math


# ----------------------------- 窗口与帧率 -----------------------------
WIDTH = 1024
HEIGHT = 768
FPS = 60
TITLE = "科技守卫家园 - 055型南昌舰指挥模拟器"


# ----------------------------- 颜色定义 -----------------------------
BLACK = (4, 9, 14)
DARK = (10, 24, 32)
PANEL = (16, 34, 43)
PANEL_EDGE = (65, 142, 152)
GREEN = (42, 255, 126)
GREEN_DIM = (20, 105, 67)
RED = (242, 71, 71)
ORANGE = (255, 145, 38)
YELLOW = (255, 230, 92)
WHITE = (230, 242, 245)
CYAN = (89, 219, 255)
BLUE = (72, 139, 255)
GRAY = (122, 141, 150)
SHIP_BLUE = (56, 101, 142)


# ----------------------------- 雷达布局 -----------------------------
# 公开资料通常不会给出055型舰载雷达的精确探测距离。
# 为了更符合大型相控阵舰“远程搜索、区域防空”的能力展示，
# 本模拟将雷达屏从300×300扩大到420×420，搜索半径由150px扩大到205px。
RADAR_CENTER = (230, 230)
RADAR_RADIUS = 205
RADAR_RANGE_KM = 1000
ORGANIC_RADAR_RANGE_KM = 450
KM_PER_PIXEL = RADAR_RANGE_KM / RADAR_RADIUS
# 1秒真实时间约等于3分钟战场时间。这样1000km雷达圈能在屏幕上可玩，
# 同时舰艇、飞机和导弹速度仍按真实量级换算。
TIME_COMPRESSION = 180
RADAR_RECT = (20, 20, 420, 420)
RADAR_SCAN_SPEED = 2.45  # 弧度/秒，符合题目要求的2~3弧度/秒


# ----------------------------- 055南昌舰真实参数 -----------------------------
SHIP_INFO = {
    "舷号": "101",
    "名称": "南昌舰",
    "满载排水量": "超12000吨",
    "舰长": "约180米",
    "舰宽": "超20米",
    "垂发系统": "112单元通用垂直发射系统，可冷热共架发射",
    "雷达系统": "346B型S波段有源相控阵雷达，X波段雷达，综合射频系统，游戏比例尺按1000km态势圈展示",
    "主炮": "130毫米舰艏主炮",
    "近防系统": "1130近防炮（理论射速11000发/分钟）+ 红旗-10近程防空导弹（24单元）",
    "导弹类型": "海红旗-9B、鹰击-18、鹰击-21、长剑-10",
    "直升机": "双机库，可搭载直-20反潜直升机",
}


# ----------------------------- 武器与得分 -----------------------------
VLS_TOTAL = 112
HHQ9B_RANGE_KM = 260
HHQ16B_RANGE_KM = 160
YJ18_RANGE_KM = 600
YJ21_RANGE_KM = 1500
CJ10_RANGE_KM = 1000
# 游戏采用一套偏综合打击任务的装载方案，合计不超过112单元通用垂发。
# 公开资料确认的是112单元通用垂发，具体战时装载比例不会公开。
HHQ9B_AMMO = 56
HHQ16B_AMMO = 12
YJ18_AMMO = 16
YJ21_AMMO = 8
CJ10_AMMO = 12
HQ10_CELLS = 24
LASER_HEAT_MAX = 100
LASER_RANGE_KM = 30
LASER_RANGE = LASER_RANGE_KM / KM_PER_PIXEL
SHIP_HEALTH = 100
MAX_FAILURES = 4

SCORE_AIRCRAFT = 10
SCORE_MISSILE = 20
FAILURE_PENALTY = 5


# ----------------------------- 目标类型 -----------------------------
TARGET_AIRCRAFT = "enemy_aircraft"
TARGET_MISSILE = "anti_ship_missile"
TARGET_SEA = "surface_target"
TARGET_LAND = "land_target"
TARGET_DECOY = "decoy_target"

TARGET_LABELS = {
    TARGET_AIRCRAFT: "敌机",
    TARGET_MISSILE: "反舰导弹",
    TARGET_SEA: "海面目标",
    TARGET_LAND: "陆上目标",
    TARGET_DECOY: "假目标",
}


# ----------------------------- 辅助函数 -----------------------------
def clamp(value, low, high):
    """限制数值范围，避免生命值、比例等显示越界。"""
    return max(low, min(high, value))


def distance(a, b):
    """计算二维距离，用于雷达探测、导弹命中和近防炮判断。"""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def km_to_px(km):
    """把真实距离换算成雷达屏像素。"""
    return km / KM_PER_PIXEL


def px_to_km(px):
    """把雷达屏像素换算成真实距离。"""
    return px * KM_PER_PIXEL


def kmh_to_px_per_sec(kmh):
    """把真实速度(km/h)按时间压缩换算为屏幕速度(px/s)。"""
    return (kmh / 3600.0) * TIME_COMPRESSION / KM_PER_PIXEL
