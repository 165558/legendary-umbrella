#!/usr/bin/env python3
"""
量子冲浪者 Quantum Surfer - 百分之百原创终端游戏
==================================================
一款科幻风格的量子状态切换游戏。
你是一个量子粒子，在量子场中穿梭。
切换量子态来吸收同色能量，躲避异色粒子与湮灭球！

操作说明：
  ← → / A D    : 左右移动
  ↑ / W / 空格 : 切换量子态 (蓝 ↔ 红)
  Q / ESC      : 退出游戏

游戏机制：
  ● 吸收同色能量球  →  +分数 (+连击)
  ● 触碰异色粒子    →  -1 生命 (连击清零)
  ● 触碰湮灭球 (◎)  →  -2 生命 (大爆炸)
  ● 收集量子跃迁 (✦) →  清屏大招，清除所有粒子并奖励分数
  ● 连击越高，得分倍率越大！
"""

import curses
import random
import time
import os
import sys
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# ============================================================
# 游戏常量
# ============================================================
GAME_TITLE = "★ 量 子 冲 浪 者 ★ QUANTUM SURFER ★"
VERSION = "v1.0 ORIGINAL"

# 颜色对编号
CP_BLUE = 1
CP_RED = 2
CP_WHITE = 3
CP_YELLOW = 4
CP_GREEN = 5
CP_CYAN = 6
CP_MAGENTA = 7
CP_DIM = 8
CP_ORANGE = 9

# 粒子类型
PT_BLUE_ENERGY = "blue_energy"      # 蓝色能量：蓝态吸收
PT_RED_ENERGY = "red_energy"        # 红色能量：红态吸收
PT_ANTI_BLUE = "anti_blue"          # 反蓝粒子：蓝态躲避
PT_ANTI_RED = "anti_red"            # 反红粒子：红态躲避
PT_ANNIHILATE = "annihilate"        # 湮灭球：双方都要躲
PT_QUANTUM_JUMP = "quantum_jump"    # 量子跃迁（大招）
PT_WAVE = "wave"                    # 量子波（视觉装饰）

# 量子态
STATE_BLUE = "blue"
STATE_RED = "red"

HIGHSCORE_FILE = "/workspace/.quantum_surfer_hs"


# ============================================================
# 数据结构
# ============================================================
@dataclass
class Particle:
    x: int
    y: float
    vy: float
    kind: str
    ch: str
    color: int
    width: int = 1

    def step(self):
        self.y += self.vy


@dataclass
class FloatingText:
    x: int
    y: float
    text: str
    color: int
    life: int = 20


@dataclass
class Game:
    # 场景尺寸
    width: int = 40
    height: int = 24

    # 玩家
    px: int = 20
    state: str = STATE_BLUE
    lives: int = 5
    score: int = 0
    combo: int = 0
    max_combo: int = 0
    level: int = 1

    # 资源
    particles: List[Particle] = field(default_factory=list)
    floats: List[FloatingText] = field(default_factory=list)
    explosions: List[Tuple[int, int, int]] = field(default_factory=list)  # x, y, life

    # 节奏
    tick: int = 0
    spawn_timer: int = 0
    screen_shake: int = 0

    # 状态
    game_over: bool = False
    paused: bool = False
    started: bool = False

    # 统计
    blue_collected: int = 0
    red_collected: int = 0
    annihilate_hits: int = 0
    jumps_used: int = 0


# ============================================================
# 辅助函数
# ============================================================
def combo_multiplier(combo: int) -> float:
    if combo < 5:
        return 1.0
    elif combo < 10:
        return 1.5
    elif combo < 20:
        return 2.0
    elif combo < 40:
        return 3.0
    elif combo < 80:
        return 5.0
    else:
        return 8.0


def load_highscore() -> int:
    try:
        if os.path.exists(HIGHSCORE_FILE):
            with open(HIGHSCORE_FILE, "r") as f:
                return int(f.read().strip() or 0)
    except Exception:
        pass
    return 0


def save_highscore(score: int):
    try:
        current = load_highscore()
        if score > current:
            with open(HIGHSCORE_FILE, "w") as f:
                f.write(str(score))
            return True
    except Exception:
        pass
    return False


# ============================================================
# 粒子生成
# ============================================================
def spawn_particle(g: Game):
    """根据等级生成随机粒子"""
    # 等级越高，生成越快
    base_speed = 0.25 + g.level * 0.03
    speed = base_speed + random.random() * 0.2

    r = random.random()
    jump_chance = 0.025
    annihilate_chance = 0.06 + g.level * 0.008  # 湮灭球随等级增加
    anti_chance = 0.28 + g.level * 0.01

    x = random.randint(1, g.width - 2)

    if r < jump_chance:
        # 量子跃迁大招
        g.particles.append(Particle(
            x=x, y=0.0, vy=speed * 0.8,
            kind=PT_QUANTUM_JUMP, ch="✦", color=CP_YELLOW
        ))
    elif r < jump_chance + annihilate_chance:
        # 湮灭球
        g.particles.append(Particle(
            x=x, y=0.0, vy=speed * 1.1,
            kind=PT_ANNIHILATE, ch="◎", color=CP_MAGENTA
        ))
    elif r < jump_chance + annihilate_chance + anti_chance:
        # 反粒子
        if random.random() < 0.5:
            g.particles.append(Particle(
                x=x, y=0.0, vy=speed,
                kind=PT_ANTI_BLUE, ch="✕", color=CP_BLUE
            ))
        else:
            g.particles.append(Particle(
                x=x, y=0.0, vy=speed,
                kind=PT_ANTI_RED, ch="✕", color=CP_RED
            ))
    else:
        # 能量球
        if random.random() < 0.5:
            g.particles.append(Particle(
                x=x, y=0.0, vy=speed,
                kind=PT_BLUE_ENERGY, ch="●", color=CP_BLUE
            ))
        else:
            g.particles.append(Particle(
                x=x, y=0.0, vy=speed,
                kind=PT_RED_ENERGY, ch="●", color=CP_RED
            ))


# ============================================================
# 碰撞 & 游戏逻辑
# ============================================================
def add_float(g: Game, x: int, y: int, text: str, color: int):
    g.floats.append(FloatingText(x=x, y=float(y), text=text, color=color))


def trigger_explosion(g: Game, x: int, y: int, size: int = 3):
    for i in range(size):
        for j in range(size):
            if random.random() < 0.6:
                g.explosions.append((
                    x - size // 2 + i,
                    y - size // 2 + j,
                    random.randint(5, 12)
                ))
    g.screen_shake = max(g.screen_shake, size * 2)


def quantum_jump(g: Game, stdscr):
    """清屏大招：清除所有粒子并奖励分数"""
    g.jumps_used += 1
    bonus = 0
    cleared = 0
    for p in g.particles:
        if p.kind == PT_BLUE_ENERGY or p.kind == PT_RED_ENERGY:
            bonus += 15
            cleared += 1
        elif p.kind == PT_ANNIHILATE:
            bonus += 30
            cleared += 1
        else:
            cleared += 1
        # 大爆炸视觉
        trigger_explosion(g, p.x, int(p.y), size=2)
    g.particles.clear()
    g.score += bonus
    add_float(g, g.width // 2 - 6, g.height // 2,
              f"量子跃迁! +{bonus}", CP_YELLOW)
    add_float(g, g.width // 2 - 8, g.height // 2 + 1,
              f"清除 {cleared} 个粒子", CP_CYAN)


def update(g: Game, stdscr):
    """推进一帧游戏逻辑"""
    g.tick += 1

    # 生成粒子
    spawn_interval = max(3, 14 - g.level)
    g.spawn_timer += 1
    if g.spawn_timer >= spawn_interval:
        g.spawn_timer = 0
        spawn_particle(g)
        # 高等级偶尔双发
        if g.level >= 5 and random.random() < 0.25:
            spawn_particle(g)

    # 升级判定
    new_level = 1 + g.score // 500
    if new_level > g.level:
        g.level = new_level
        add_float(g, g.width // 2 - 5, g.height // 2 - 2,
                  f"LEVEL {g.level}!", CP_GREEN)

    # 更新粒子
    player_y = g.height - 2
    player_x = g.px
    remaining: List[Particle] = []

    for p in g.particles:
        p.step()
        py = int(p.y)

        # 出界
        if py >= g.height:
            continue

        # 碰撞判定：玩家层
        if py == player_y and abs(p.x - player_x) <= 1:
            kind = p.kind
            # 根据状态和类型处理
            if kind == PT_BLUE_ENERGY:
                if g.state == STATE_BLUE:
                    g.combo += 1
                    g.max_combo = max(g.max_combo, g.combo)
                    mult = combo_multiplier(g.combo)
                    pts = int(10 * mult)
                    g.score += pts
                    g.blue_collected += 1
                    add_float(g, p.x, py, f"+{pts}", CP_CYAN)
                    trigger_explosion(g, p.x, py, size=1)
                    continue  # 吸收，移除
                else:
                    pass  # 不匹配：直接穿过？不，能量球都可以尝试躲开，不扣血
            elif kind == PT_RED_ENERGY:
                if g.state == STATE_RED:
                    g.combo += 1
                    g.max_combo = max(g.max_combo, g.combo)
                    mult = combo_multiplier(g.combo)
                    pts = int(10 * mult)
                    g.score += pts
                    g.red_collected += 1
                    add_float(g, p.x, py, f"+{pts}", CP_ORANGE)
                    trigger_explosion(g, p.x, py, size=1)
                    continue
            elif kind == PT_ANTI_BLUE:
                if g.state == STATE_BLUE:
                    # 对蓝态有害
                    g.lives -= 1
                    g.combo = 0
                    add_float(g, p.x, py, "-1 HP!", CP_RED)
                    trigger_explosion(g, p.x, py, size=3)
                    continue
            elif kind == PT_ANTI_RED:
                if g.state == STATE_RED:
                    g.lives -= 1
                    g.combo = 0
                    add_float(g, p.x, py, "-1 HP!", CP_RED)
                    trigger_explosion(g, p.x, py, size=3)
                    continue
            elif kind == PT_ANNIHILATE:
                g.lives -= 2
                g.combo = 0
                g.annihilate_hits += 1
                add_float(g, p.x, py, "湮 灭!", CP_MAGENTA)
                trigger_explosion(g, p.x, py, size=5)
                continue
            elif kind == PT_QUANTUM_JUMP:
                quantum_jump(g, stdscr)
                continue

        remaining.append(p)
    g.particles = remaining

    # 浮动文字寿命
    g.floats = [f for f in g.floats if f.life > 0]
    for f in g.floats:
        f.y -= 0.3
        f.life -= 1

    # 爆炸
    g.explosions = [(x, y, l - 1) for x, y, l in g.explosions if l > 0]

    # 屏震衰减
    if g.screen_shake > 0:
        g.screen_shake -= 1

    # 生命耗尽
    if g.lives <= 0:
        g.game_over = True


# ============================================================
# 渲染
# ============================================================
def draw_border(stdscr, g: Game, origin_y: int, origin_x: int):
    """画外框"""
    w = g.width + 2
    h = g.height + 2
    # 顶部
    stdscr.addstr(origin_y, origin_x, "╔" + "═" * (w - 2) + "╗",
                  curses.color_pair(CP_DIM))
    # 底部
    stdscr.addstr(origin_y + h - 1, origin_x, "╚" + "═" * (w - 2) + "╝",
                  curses.color_pair(CP_DIM))
    # 竖边
    for i in range(1, h - 1):
        stdscr.addstr(origin_y + i, origin_x, "║", curses.color_pair(CP_DIM))
        stdscr.addstr(origin_y + i, origin_x + w - 1, "║",
                      curses.color_pair(CP_DIM))


def safe_addstr(stdscr, y: int, x: int, s: str, attr: int = 0):
    """安全输出（忽略越界）"""
    try:
        stdscr.addstr(y, x, s, attr)
    except curses.error:
        pass


def render(stdscr, g: Game, highscore: int):
    stdscr.erase()
    sh, sw = stdscr.getmaxyx()
    # 整体居中
    total_w = g.width + 2 + 22  # 游戏区 + 侧边栏
    total_h = g.height + 2
    origin_x = max(2, (sw - total_w) // 2)
    origin_y = max(1, (sh - total_h) // 2)

    # 屏震
    shake_x = 0
    shake_y = 0
    if g.screen_shake > 0:
        shake_x = random.randint(-1, 1)
        shake_y = random.randint(-1, 1)
    origin_x += shake_x
    origin_y += shake_y

    # 标题
    title = f" {GAME_TITLE} {VERSION} "
    safe_addstr(stdscr, origin_y - 1,
                origin_x + (total_w - len(title)) // 2, title,
                curses.color_pair(CP_YELLOW) | curses.A_BOLD)

    # 画边框
    draw_border(stdscr, g, origin_y, origin_x)

    # 内部坐标偏移
    inner_x = origin_x + 1
    inner_y = origin_y + 1

    # 1) 背景量子波动线（视觉装饰）
    bg_color = curses.color_pair(CP_DIM)
    for row in range(g.height):
        if (row + g.tick // 3) % 4 == 0:
            line_ch = ""
            for col in range(g.width):
                if (col * 3 + row + g.tick // 2) % 11 == 0:
                    line_ch += "·"
                else:
                    line_ch += " "
            safe_addstr(stdscr, inner_y + row, inner_x, line_ch, bg_color)

    # 2) 粒子
    for p in g.particles:
        y = int(p.y)
        if 0 <= y < g.height and 0 <= p.x < g.width:
            attr = curses.color_pair(p.color)
            if p.kind == PT_QUANTUM_JUMP:
                attr |= curses.A_BOLD
            if p.kind == PT_ANNIHILATE and g.tick % 6 < 3:
                attr |= curses.A_REVERSE
            safe_addstr(stdscr, inner_y + y, inner_x + p.x, p.ch, attr)

    # 3) 爆炸
    for (ex, ey, life) in g.explosions:
        if 0 <= ey < g.height and 0 <= ex < g.width:
            c = "*+x·"[min(3, 4 - life // 3)]
            col = CP_YELLOW if life > 6 else (CP_ORANGE if life > 3 else CP_RED)
            safe_addstr(stdscr, inner_y + ey, inner_x + ex, c,
                        curses.color_pair(col) | curses.A_BOLD)

    # 4) 玩家
    py = g.height - 2
    pcol = CP_BLUE if g.state == STATE_BLUE else CP_RED
    pchar = "▼"
    # 底座 (冲浪板)
    board = "■■■"
    safe_addstr(stdscr, inner_y + py, inner_x + g.px - 1, board,
                curses.color_pair(pcol) | curses.A_BOLD)
    # 玩家核心
    glow = curses.A_BOLD
    if g.tick % 10 < 5:
        glow |= curses.A_REVERSE
    safe_addstr(stdscr, inner_y + py - 1, inner_x + g.px, pchar,
                curses.color_pair(pcol) | glow)

    # 5) 状态指示条（玩家头顶）
    state_label = " 蓝态 BLUE " if g.state == STATE_BLUE else " 红态 RED  "
    sc = CP_CYAN if g.state == STATE_BLUE else CP_ORANGE
    safe_addstr(stdscr, inner_y + py - 3,
                inner_x + g.px - len(state_label) // 2,
                state_label, curses.color_pair(sc) | curses.A_BOLD)

    # 6) 浮动文字
    for f in g.floats:
        y = int(f.y)
        if 0 <= y < g.height and 0 <= f.x < g.width:
            alpha = curses.A_BOLD if f.life > 10 else 0
            safe_addstr(stdscr, inner_y + y, inner_x + f.x, f.text,
                        curses.color_pair(f.color) | alpha)

    # ===== 侧边栏 HUD =====
    hud_x = origin_x + g.width + 4
    hud_y = origin_y + 1

    def hud_line(y_off, label, value, color=CP_WHITE):
        safe_addstr(stdscr, hud_y + y_off, hud_x, label,
                    curses.color_pair(CP_DIM))
        safe_addstr(stdscr, hud_y + y_off, hud_x + 12, str(value),
                    curses.color_pair(color) | curses.A_BOLD)

    hud_line(0, "分数 SCORE :", g.score, CP_YELLOW)
    hud_line(1, "最高 HIGH  :", max(highscore, g.score), CP_GREEN)
    hud_line(2, "等级 LEVEL :", g.level, CP_CYAN)
    hud_line(3, "生命 LIVES :", "♥ " * max(0, g.lives), CP_RED)
    hud_line(4, "连击 COMBO :", g.combo,
             CP_MAGENTA if g.combo >= 10 else CP_ORANGE)
    mult = combo_multiplier(g.combo)
    hud_line(5, "倍率 MULT  :", f"x{mult:.1f}", CP_MAGENTA)
    hud_line(6, "────────────", "────────────", CP_DIM)
    hud_line(7, "蓝能量     :", g.blue_collected, CP_CYAN)
    hud_line(8, "红能量     :", g.red_collected, CP_ORANGE)
    hud_line(9, "湮灭击中   :", g.annihilate_hits, CP_MAGENTA)
    hud_line(10, "跃迁次数   :", g.jumps_used, CP_YELLOW)
    hud_line(11, "最高连击   :", g.max_combo, CP_GREEN)

    # 操作提示
    tip_y = hud_y + 13
    tips = [
        ("← → / A D", CP_WHITE, " 移动"),
        ("↑ / W / ␣", CP_WHITE, " 切换态"),
        ("收集 ●", CP_BLUE, f" 蓝态吸收"),
        ("收集 ●", CP_RED, f" 红态吸收"),
        ("躲避 ✕", CP_WHITE, f" 反粒子"),
        ("躲避 ◎", CP_MAGENTA, f" 湮灭球"),
        ("拾取 ✦", CP_YELLOW, f" 量子跃迁"),
    ]
    for i, (k, c, t) in enumerate(tips):
        safe_addstr(stdscr, tip_y + i, hud_x, k,
                    curses.color_pair(c) | curses.A_BOLD)
        safe_addstr(stdscr, tip_y + i, hud_x + 10, t,
                    curses.color_pair(CP_DIM))

    # 底部提示
    if not g.game_over:
        safe_addstr(stdscr, origin_y + g.height + 2, origin_x,
                    " 按 Q / ESC 退出  |  P 暂停  |  切换量子态来匹配能量颜色！",
                    curses.color_pair(CP_DIM))

    stdscr.refresh()


# ============================================================
# 开始界面 & 结束界面
# ============================================================
def draw_start_screen(stdscr, g: Game, highscore: int):
    sh, sw = stdscr.getmaxyx()
    stdscr.erase()
    # 动态粒子背景
    for i in range(sh):
        s = ""
        for j in range(sw - 1):
            r = (i * 7 + j * 13 + g.tick) % 97
            if r < 2:
                s += random.choice("●◎✕✦·")
            else:
                s += " "
        col = [CP_BLUE, CP_RED, CP_CYAN, CP_MAGENTA, CP_YELLOW][(i + g.tick // 5) % 5]
        try:
            stdscr.addstr(i, 0, s, curses.color_pair(col))
        except curses.error:
            pass

    title_lines = [
        "",
        "    ██████╗ ██╗   ██╗ █████╗ ███╗   ██╗████████╗██╗   ██╗███╗   ███╗    ",
        "   ██╔═══██╗██║   ██║██╔══██╗████╗  ██║╚══██╔══╝██║   ██║████╗ ████║    ",
        "   ██║   ██║██║   ██║███████║██╔██╗ ██║   ██║   ██║   ██║██╔████╔██║    ",
        "   ██║▄▄ ██║██║   ██║██╔══██║██║╚██╗██║   ██║   ██║   ██║██║╚██╔╝██║    ",
        "   ╚██████╔╝╚██████╔╝██║  ██║██║ ╚████║   ██║   ╚██████╔╝██║ ╚═╝ ██║    ",
        "    ╚══▀▀═╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝    ╚═════╝ ╚═╝     ╚═╝    ",
        "",
        "   ★ 量 子 冲 浪 者  |  Q U A N T U M   S U R F E R  ★  ",
        "",
    ]
    ty = max(2, (sh - 20) // 2)
    for i, line in enumerate(title_lines):
        col = CP_BLUE if (i + g.tick // 8) % 2 == 0 else CP_RED
        safe_addstr(stdscr, ty + i, max(0, (sw - len(line)) // 2), line,
                    curses.color_pair(col) | curses.A_BOLD)

    info_y = ty + len(title_lines) + 1
    info_lines = [
        (f"  最高分 HIGH SCORE : {highscore}  ", CP_YELLOW),
        (f"  版本 {VERSION} · 百分之百原创  ", CP_GREEN),
        ("", 0),
        ("  ═══════════════  游 戏 玩 法  ═══════════════", CP_WHITE),
        ("", 0),
        ("  你是一个在量子场中穿梭的粒子冲浪者！", CP_CYAN),
        ("  ● 吸收 同色能量球 → 获得分数与连击  ", CP_WHITE),
        ("  ✕ 躲避 异色反粒子 → 免受生命值伤害  ", CP_WHITE),
        ("  ◎ 逃离 湮灭球     → 超大范围爆炸！  ", CP_WHITE),
        ("  ✦ 拾取 量子跃迁   → 清屏大招奖励分  ", CP_WHITE),
        ("  连击越高 → 得分倍率越大 (最高 x8.0)  ", CP_MAGENTA),
        ("", 0),
        ("  ═══════════════  操 作 说 明  ═══════════════", CP_WHITE),
        ("", 0),
        ("  ← →  或  A D     :  左右移动冲浪板  ", CP_WHITE),
        ("  ↑ / W / 空格键    :  切换 蓝态 ↔ 红态  ", CP_WHITE),
        ("  P                :  暂停 / 继续      ", CP_WHITE),
        ("  Q 或 ESC         :  退出游戏         ", CP_WHITE),
        ("", 0),
        ("  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", CP_DIM),
    ]
    for i, (text, col) in enumerate(info_lines):
        attr = curses.color_pair(col) if col else 0
        if col in (CP_WHITE, CP_YELLOW, CP_CYAN, CP_MAGENTA, CP_GREEN):
            attr |= curses.A_BOLD
        safe_addstr(stdscr, info_y + i, max(0, (sw - 52) // 2), text, attr)

    blink = g.tick % 40 < 25
    if blink:
        prompt = "  >>>  按 任意键 开始游戏 (SPACE/回车 快速开始)  <<<  "
        safe_addstr(stdscr, info_y + len(info_lines) + 1,
                    max(0, (sw - len(prompt)) // 2), prompt,
                    curses.color_pair(CP_YELLOW) | curses.A_BOLD | curses.A_REVERSE)

    stdscr.refresh()


def draw_game_over(stdscr, g: Game, highscore: int, new_record: bool):
    sh, sw = stdscr.getmaxyx()
    stdscr.erase()
    # 背景
    for i in range(sh):
        s = ""
        for j in range(sw - 1):
            r = (i * 5 + j * 11 + g.tick) % 73
            if r == 0:
                s += "✕"
            elif r == 1:
                s += "◎"
            else:
                s += " "
        try:
            stdscr.addstr(i, 0, s, curses.color_pair(CP_RED if i % 2 else CP_DIM))
        except curses.error:
            pass

    ty = max(2, (sh - 18) // 2)
    go_title = [
        "",
        "    ██████╗  █████╗ ███╗   ███╗███████╗     ██████╗ ██╗   ██╗███████╗██████╗ ",
        "   ██╔════╝ ██╔══██╗████╗ ████║██╔════╝    ██╔═══██╗██║   ██║██╔════╝██╔══██╗",
        "   ██║  ███╗███████║██╔████╔██║█████╗      ██║   ██║██║   ██║█████╗  ██████╔╝",
        "   ██║   ██║██╔══██║██║╚██╔╝██║██╔══╝      ██║   ██║╚██╗ ██╔╝██╔══╝  ██╔══██╗",
        "   ╚██████╔╝██║  ██║██║ ╚═╝ ██║███████╗    ╚██████╔╝ ╚████╔╝ ███████╗██║  ██║",
        "    ╚═════╝ ╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝     ╚═════╝   ╚═══╝  ╚══════╝╚═╝  ╚═╝",
        "",
    ]
    for i, line in enumerate(go_title):
        safe_addstr(stdscr, ty + i, max(0, (sw - len(line)) // 2), line,
                    curses.color_pair(CP_RED) | curses.A_BOLD)

    iy = ty + len(go_title) + 1
    panel_width = 48
    px0 = max(0, (sw - panel_width) // 2)

    def panel_line(y, label, value, col=CP_WHITE):
        lbl = f"  {label:<18}"
        val = f"{str(value):>20}  "
        safe_addstr(stdscr, iy + y, px0,
                    "║" + " " * (panel_width - 2) + "║",
                    curses.color_pair(CP_DIM))
        safe_addstr(stdscr, iy + y, px0 + 1, lbl.strip(),
                    curses.color_pair(CP_CYAN) | curses.A_BOLD)
        safe_addstr(stdscr, iy + y, px0 + panel_width - len(val) - 1,
                    val.strip(), curses.color_pair(col) | curses.A_BOLD)

    safe_addstr(stdscr, iy, px0, "╔" + "═" * (panel_width - 2) + "╗",
                curses.color_pair(CP_DIM))
    if new_record:
        safe_addstr(stdscr, iy, px0 + (panel_width - 14) // 2,
                    "★ 新 纪 录 ★",
                    curses.color_pair(CP_YELLOW) | curses.A_BOLD | curses.A_REVERSE)

    stats = [
        ("最终分数", g.score, CP_YELLOW),
        ("最高分", max(highscore, g.score), CP_GREEN),
        ("到达等级", g.level, CP_CYAN),
        ("最高连击", g.max_combo, CP_MAGENTA),
        ("收集蓝能量", g.blue_collected, CP_CYAN),
        ("收集红能量", g.red_collected, CP_ORANGE),
        ("湮灭命中", g.annihilate_hits, CP_RED),
        ("使用跃迁", g.jumps_used, CP_YELLOW),
    ]
    for idx, (l, v, c) in enumerate(stats):
        panel_line(idx + 1, l, v, c)
    safe_addstr(stdscr, iy + len(stats) + 1, px0,
                "╚" + "═" * (panel_width - 2) + "╝",
                curses.color_pair(CP_DIM))

    blink = g.tick % 40 < 25
    if blink:
        prompt = "  >>>  按 R 重新开始  |  按 Q / ESC 退出游戏  <<<  "
        safe_addstr(stdscr, iy + len(stats) + 3,
                    max(0, (sw - len(prompt)) // 2), prompt,
                    curses.color_pair(CP_GREEN) | curses.A_BOLD | curses.A_REVERSE)

    stdscr.refresh()


def draw_paused(stdscr, g: Game):
    sh, sw = stdscr.getmaxyx()
    overlay_y = sh // 2 - 3
    overlay_x = (sw - 30) // 2
    box_lines = [
        "╔════════════════════════════╗",
        "║                            ║",
        "║        ⏸ 暂 停 中 ⏸        ║",
        "║                            ║",
        "║    按 P 或 任意键继续      ║",
        "║                            ║",
        "╚════════════════════════════╝",
    ]
    for i, line in enumerate(box_lines):
        col = CP_YELLOW if i in (2, 4) else CP_WHITE
        safe_addstr(stdscr, overlay_y + i, overlay_x, line,
                    curses.color_pair(col) | curses.A_BOLD)
    stdscr.refresh()


# ============================================================
# 主循环
# ============================================================
def init_colors():
    curses.start_color()
    curses.use_default_colors()
    # 亮色
    curses.init_pair(CP_BLUE, curses.COLOR_CYAN, -1)
    curses.init_pair(CP_RED, curses.COLOR_RED, -1)
    curses.init_pair(CP_WHITE, curses.COLOR_WHITE, -1)
    curses.init_pair(CP_YELLOW, curses.COLOR_YELLOW, -1)
    curses.init_pair(CP_GREEN, curses.COLOR_GREEN, -1)
    curses.init_pair(CP_CYAN, curses.COLOR_CYAN, -1)
    curses.init_pair(CP_MAGENTA, curses.COLOR_MAGENTA, -1)
    curses.init_pair(CP_DIM, 8, -1)  # 灰色
    curses.init_pair(CP_ORANGE, 208, -1) if curses.COLORS >= 256 else \
        curses.init_pair(CP_ORANGE, curses.COLOR_YELLOW, -1)


def main(stdscr):
    # 初始化 curses
    init_colors()
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(30)  # ~33fps

    g = Game()
    highscore = load_highscore()
    new_record = False

    phase = "start"  # start / playing / paused / gameover

    while True:
        try:
            key = stdscr.getch()
        except Exception:
            key = -1

        # 通用退出
        if key in (ord('q'), ord('Q'), 27):  # ESC
            if phase == "gameover":
                save_highscore(g.score)
            break

        # ----- 开始界面 -----
        if phase == "start":
            g.tick += 1
            if g.tick % 1 == 0:
                # 生成一些装饰粒子（但不影响游戏）
                pass
            draw_start_screen(stdscr, g, highscore)
            if key != -1 and key != curses.KEY_RESIZE:
                # 开始新游戏
                g = Game()
                g.started = True
                phase = "playing"
            continue

        # ----- 游戏结束 -----
        if phase == "gameover":
            g.tick += 1
            draw_game_over(stdscr, g, highscore, new_record)
            if key in (ord('r'), ord('R')):
                g = Game()
                g.started = True
                new_record = False
                phase = "playing"
            continue

        # ----- 游戏中 -----
        if phase == "playing":
            # 暂停切换
            if key in (ord('p'), ord('P')):
                phase = "paused"
                continue

            # 移动
            if key in (curses.KEY_LEFT, ord('a'), ord('A')):
                g.px = max(1, g.px - 1)
            elif key in (curses.KEY_RIGHT, ord('d'), ord('D')):
                g.px = min(g.width - 2, g.px + 1)
            # 切换量子态
            elif key in (curses.KEY_UP, ord('w'), ord('W'), ord(' ')):
                g.state = STATE_RED if g.state == STATE_BLUE else STATE_BLUE
                add_float(g, g.px, g.height - 4,
                          "态切换!" if g.state == STATE_BLUE else "态切换!",
                          CP_CYAN if g.state == STATE_BLUE else CP_ORANGE)

            # 推进逻辑
            update(g, stdscr)
            # 渲染
            render(stdscr, g, highscore)

            if g.game_over:
                new_record = save_highscore(g.score)
                if new_record:
                    highscore = g.score
                phase = "gameover"
                g.tick = 0
            continue

        # ----- 暂停 -----
        if phase == "paused":
            render(stdscr, g, highscore)
            draw_paused(stdscr, g)
            if key != -1 and key != curses.KEY_RESIZE:
                phase = "playing"
            continue


def run():
    # 尝试设置终端大小偏好（不强制）
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__)
        return
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        pass
    # 游戏结束后简单总结
    hs = load_highscore()
    print()
    print("=" * 58)
    print(f"  ★ 量子冲浪者 Quantum Surfer 感谢您的游玩！")
    print(f"  ★ 最高分 HIGH SCORE : {hs}")
    print(f"  ★ 游戏代码: /workspace/quantum_surfer.py  (百分之百原创)")
    print("=" * 58)


if __name__ == "__main__":
    run()
