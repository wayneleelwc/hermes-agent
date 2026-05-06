#!/usr/bin/env python
"""Generate hand-drawn style infographics for Hermes memory system article.

Style: Notion hand-drawn infographic style
- Yellow primary (#F5C518) + black accents
- xkcd sketch mode for loose, hand-drawn feel
- 16:9 aspect ratio, Chinese labels
- Lots of whitespace, minimal decoration
"""

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__)) + '/images'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Color palette
YELLOW = '#F5C518'
YELLOW_LIGHT = '#FFF8DC'
BLACK = '#1A1A1A'
GRAY = '#888888'
WHITE = '#FFFEF9'
RED = '#E05555'
GREEN = '#4CAF50'
BLUE = '#5B9BD5'

plt.rcParams['font.family'] = ['Microsoft YaHei', 'SimHei', 'sans-serif']
plt.rcParams['font.size'] = 12
plt.rcParams['axes.unicode_minus'] = False


def setup_figure(title=None):
    """Setup 16:9 figure with hand-drawn style."""
    fig, ax = plt.subplots(figsize=(16, 9))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.axis('off')
    ax.set_facecolor(WHITE)
    fig.patch.set_facecolor(WHITE)
    return fig, ax


def draw_hand_box(ax, x, y, w, h, color=BLACK, fill=None, lw=2, style='round'):
    """Draw a hand-drawn style box."""
    n_pts = 30
    jitter = 0.03
    if style == 'round':
        # Draw rounded rectangle with hand-drawn jitter
        pts_x = []
        pts_y = []
        # Top edge
        for i in range(n_pts):
            t = i / (n_pts - 1)
            pts_x.append(x + t * w + np.random.uniform(-jitter, jitter))
            pts_y.append(y + h + np.random.uniform(-jitter, jitter))
        # Right edge
        for i in range(n_pts):
            t = i / (n_pts - 1)
            pts_x.append(x + w + np.random.uniform(-jitter, jitter))
            pts_y.append(y + (1-t) * h + np.random.uniform(-jitter, jitter))
        # Bottom edge
        for i in range(n_pts):
            t = i / (n_pts - 1)
            pts_x.append(x + (1-t) * w + np.random.uniform(-jitter, jitter))
            pts_y.append(y + np.random.uniform(-jitter, jitter))
        # Left edge
        for i in range(n_pts):
            t = i / (n_pts - 1)
            pts_x.append(x + np.random.uniform(-jitter, jitter))
            pts_y.append(y + t * h + np.random.uniform(-jitter, jitter))
        
        if fill:
            ax.fill(pts_x, pts_y, color=fill, alpha=0.8, zorder=1)
        ax.plot(pts_x, pts_y, color=color, lw=lw, zorder=2)
    else:
        rect = mpatches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.1",
            facecolor=fill if fill else 'none',
            edgecolor=color,
            linewidth=lw,
            zorder=1
        )
        ax.add_patch(rect)


def draw_hand_arrow(ax, x1, y1, x2, y2, color=BLACK, lw=2):
    """Draw a hand-drawn arrow."""
    n_pts = 20
    jitter = 0.04
    xs = []
    ys = []
    for i in range(n_pts):
        t = i / (n_pts - 1)
        xs.append(x1 + t * (x2 - x1) + np.random.uniform(-jitter, jitter))
        ys.append(y1 + t * (y2 - y1) + np.random.uniform(-jitter, jitter))
    ax.plot(xs, ys, color=color, lw=lw, zorder=1)
    # Arrowhead
    dx = x2 - x1
    dy = y2 - y1
    length = np.sqrt(dx*dx + dy*dy)
    if length > 0:
        dx, dy = dx/length, dy/length
        ax.plot([x2, x2 - 0.3*dx + 0.15*dy], [y2, y2 - 0.3*dy - 0.15*dx], color=color, lw=lw, zorder=1)
        ax.plot([x2, x2 - 0.3*dx - 0.15*dy], [y2, y2 - 0.3*dy + 0.15*dx], color=color, lw=lw, zorder=1)


def draw_yellow_dot(ax, x, y, size=0.15):
    """Draw a yellow accent dot."""
    circle = plt.Circle((x, y), size, color=YELLOW, zorder=5)
    ax.add_patch(circle)


# ============================================================
# Image 1: Cover - Title page
# ============================================================
def generate_cover():
    fig, ax = setup_figure()
    
    # Decorative yellow strip at top
    ax.fill_between([0, 16], [8.8, 8.8], [9, 9], color=YELLOW, alpha=0.3)
    
    # Main title
    ax.text(8, 6.5, 'Hermes Agent', fontsize=52, fontweight='bold',
            color=BLACK, ha='center', va='center')
    ax.text(8, 5.5, '记忆与知识系统', fontsize=44, fontweight='bold',
            color=BLACK, ha='center', va='center')
    
    # Yellow underline
    ax.plot([3.5, 12.5], [4.9, 4.9], color=YELLOW, lw=8, solid_capstyle='round')
    
    # Subtitle
    ax.text(8, 4.2, '双层架构与自进化闭环', fontsize=22, color=GRAY, ha='center', va='center')
    
    # Decorative elements - hand-drawn icons
    # Brain icon (simplified)
    draw_hand_box(ax, 6.5, 2.5, 3, 1.2, color=YELLOW, fill=YELLOW_LIGHT)
    ax.text(8, 3.1, '记忆 · 知识 · 进化', fontsize=14, color=BLACK, ha='center', va='center')
    
    # Decorative dots
    for x_pos in [2, 14]:
        draw_yellow_dot(ax, x_pos, 8.2, 0.2)
    
    # Series info
    ax.text(8, 1.8, 'Hermes Agent 深度拆解 · 第 03 篇', fontsize=13, color=GRAY, ha='center', va='center')
    
    # Bottom yellow accent line
    ax.fill_between([0, 16], [0.3, 0.3], [0, 0], color=YELLOW, alpha=0.2)
    
    plt.tight_layout(pad=0)
    path = os.path.join(OUTPUT_DIR, '03-记忆与知识系统·封面_01.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
    plt.close(fig)
    print(f'Generated: {path}')


# ============================================================
# Image 2: Architecture overview - 4 layers
# ============================================================
def generate_architecture_overview():
    fig, ax = setup_figure()
    
    # Title
    ax.text(8, 8.5, 'Hermes 记忆与知识系统全景', fontsize=28, fontweight='bold',
            color=BLACK, ha='center', va='center')
    ax.text(8, 7.9, '四层协同运转的知识转化体系', fontsize=14, color=GRAY, ha='center', va='center')
    
    # Layer boxes
    layers = [
        ('Layer 4: Curator 自主知识管家', '7天周期 · 扫描→评分→合并→清理→报告', 0.8, 2.0, YELLOW),
        ('Layer 3: Skills 过程性知识', 'Review Fork 审视 → 六状态生命周期', 2.8, 2.0, '#E8C547'),
        ('Layer 2: External Providers 可插拔智能后端', 'Honcho · Mem0 · Hindsight · Supermemory', 4.8, 2.0, '#D4A017'),
        ('Layer 1: Built-in Memory 声明性基座', 'MEMORY.md + USER.md → MemoryStore 文件基座', 6.8, 2.0, '#B8860B'),
    ]
    
    for title, desc, y, h, color in layers:
        alpha = 0.15 + 0.08 * (6.8 - y) / 6
        # Draw box with increasing opacity
        draw_hand_box(ax, 2, y, 12, h, color=color, fill=color, lw=2.5)
        ax.text(3, y + h/2 + 0.25, title, fontsize=16, fontweight='bold',
                color=BLACK, ha='left', va='center')
        ax.text(3, y + h/2 - 0.35, desc, fontsize=11, color=GRAY, ha='left', va='center')
    
    # Downward arrows between layers
    for y_from in [4.0, 3.0, 2.0]:
        draw_hand_arrow(ax, 8, y_from + 0.1, 8, y_from + 0.6, color=YELLOW, lw=3)
    
    # Left side labels
    ax.text(0.5, 7.3, '自进化', fontsize=12, color=GRAY, ha='center', va='center', rotation=90)
    ax.text(0.5, 3.3, '存储', fontsize=12, color=GRAY, ha='center', va='center', rotation=90)
    
    # Right side annotation
    ax.text(14.5, 7.3, '主动维护', fontsize=11, color=GRAY, ha='center', va='center')
    ax.text(14.5, 3.3, '被动记录', fontsize=11, color=GRAY, ha='center', va='center')
    draw_hand_arrow(ax, 14.5, 6.8, 14.5, 4.0, color=GRAY, lw=1.5)
    
    # Bottom note
    ax.text(8, 0.4, 'MemoryManager 编排器统一调度 · 广播 + 容错隔离模式', 
            fontsize=12, color=GRAY, ha='center', va='center', style='italic')
    
    plt.tight_layout(pad=0)
    path = os.path.join(OUTPUT_DIR, '03-记忆与知识系统·知识系统全景_02.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
    plt.close(fig)
    print(f'Generated: {path}')


# ============================================================
# Image 3: MemoryProvider lifecycle - 7 methods
# ============================================================
def generate_provider_lifecycle():
    fig, ax = setup_figure()
    
    ax.text(8, 8.5, 'MemoryProvider 生命周期', fontsize=28, fontweight='bold',
            color=BLACK, ha='center', va='center')
    ax.text(8, 7.8, '抽象基类定义的 7 个核心方法 + 编排时序', fontsize=14, color=GRAY, ha='center', va='center')
    
    # 7 lifecycle methods in a flow
    methods = [
        ('1. name()', '标识', 1.5, 'Provider 唯一名称'),
        ('2. is_available()', '可用性', 3.0, '检查 Provider 是否可用'),
        ('3. initialize()', '初始化', 4.5, '会话级初始化'),
        ('4. prefetch()', '预取', 6.0, '每轮前上下文召回'),
        ('5. sync_turn()', '同步', 7.5, '每轮后异步写入'),
        ('6. get_tool_schemas()', '工具', 9.0, '暴露给 Agent 的工具'),
        ('7. handle_tool_call()', '调度', 10.5, 'Agent 调用的工具处理'),
    ]
    
    # Draw method boxes in two rows
    for i, (name, short, x, desc) in enumerate(methods):
        row = 0 if i < 4 else 1
        col = i if row == 0 else i - 4
        
        bx = 1.5 + col * 3.2
        by = 5.5 - row * 3.0
        
        color = YELLOW if i == 3 else '#D4A017'
        alpha = 0.12 + i * 0.02
        
        draw_hand_box(ax, bx, by, 2.8, 1.8, color=color, fill=color, lw=2)
        ax.text(bx + 1.4, by + 1.2, name, fontsize=13, fontweight='bold',
                color=BLACK, ha='center', va='center')
        ax.text(bx + 1.4, by + 0.5, short, fontsize=16, fontweight='bold',
                color=YELLOW if i == 3 else BLACK, ha='center', va='center')
    
    # Connecting arrows between first row
    for i in range(3):
        x1 = 1.5 + i * 3.2 + 2.8
        x2 = x1 + 0.4
        draw_hand_arrow(ax, x1, 6.4, x2, 6.4, color=YELLOW, lw=2)
    
    # Second row arrows
    for i in range(3):
        x1 = 1.5 + i * 3.2 + 2.8
        x2 = x1 + 0.4
        draw_hand_arrow(ax, x1, 3.4, x2, 3.4, color=YELLOW, lw=2)
    
    # Down arrow between rows
    draw_hand_arrow(ax, 5, 5.3, 5, 4.7, color=YELLOW, lw=2.5)
    
    # Key constraint note
    ax.text(8, 1.5, '关键约束：一次只能激活一个 External Provider（防止 Schema 膨胀）',
            fontsize=13, color=RED, ha='center', va='center')
    
    # shutdown note
    ax.text(8, 0.8, 'shutdown() 收尾 · queue_prefetch() 为下一轮排队 · 所有方法按序编排',
            fontsize=11, color=GRAY, ha='center', va='center', style='italic')
    
    plt.tight_layout(pad=0)
    path = os.path.join(OUTPUT_DIR, '03-记忆与知识系统·MemoryProvider生命周期_03.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
    plt.close(fig)
    print(f'Generated: {path}')


# ============================================================
# Image 4: Honcho vs Mem0 comparison
# ============================================================
def generate_provider_comparison():
    fig, ax = setup_figure()
    
    ax.text(8, 8.5, 'Provider 对比：Honcho vs Mem0', fontsize=28, fontweight='bold',
            color=BLACK, ha='center', va='center')
    ax.text(8, 7.8, '两种截然不同的记忆哲学', fontsize=14, color=GRAY, ha='center', va='center')
    
    # Two columns
    col1_x, col2_x = 2.5, 9.5
    col_w = 5.0
    
    # Honcho column header
    draw_hand_box(ax, col1_x, 6.5, col_w, 1.0, color=YELLOW, fill=YELLOW, lw=2.5)
    ax.text(col1_x + col_w/2, 7.0, 'Honcho · 辩证建模', fontsize=18, fontweight='bold',
            color=BLACK, ha='center', va='center')
    
    # Mem0 column header
    draw_hand_box(ax, col2_x, 6.5, col_w, 1.0, color='#4A90D9', fill='#4A90D9', lw=2.5)
    ax.text(col2_x + col_w/2, 7.0, 'Mem0 · 事实提取', fontsize=18, fontweight='bold',
            color=WHITE, ha='center', va='center')
    
    # Comparison rows
    rows_data = [
        ('核心理念', '辩证用户建模（dialectic）', '服务端事实提取'),
        ('记忆形式', '会话级用户表示 + peer card', '结构化事实条目'),
        ('写入策略', '每轮 user/assistant 对', 'add() 写入，infer=True 自动提取'),
        ('召回方式', 'context() 返回当前表示', 'search() 语义搜索+重排序'),
        ('工具数量', '5 个工具', '3 个工具'),
        ('特色能力', '用户画像、推理问答', '自动去重、关键词提取'),
    ]
    
    for i, (label, honcho_val, mem0_val) in enumerate(rows_data):
        y = 5.8 - i * 0.85
        # Row background
        bg_color = YELLOW_LIGHT if i % 2 == 0 else WHITE
        ax.fill_between([col1_x, col1_x + col_w], [y-0.35, y-0.35], [y+0.35, y+0.35], 
                       color=bg_color, alpha=0.5, zorder=0)
        ax.fill_between([col2_x, col2_x + col_w], [y-0.35, y-0.35], [y+0.35, y+0.35],
                       color=bg_color, alpha=0.5, zorder=0)
        
        # Label
        ax.text(0.8, y, label, fontsize=12, fontweight='bold', color=BLACK, ha='left', va='center')
        
        # Honcho value
        ax.text(col1_x + col_w/2, y, honcho_val, fontsize=12, color=BLACK, ha='center', va='center')
        
        # Mem0 value
        ax.text(col2_x + col_w/2, y, mem0_val, fontsize=12, color=BLACK, ha='center', va='center')
        
        # Divider line between columns
        ax.plot([8, 8], [y-0.35, y+0.35], color=GRAY, lw=0.5, alpha=0.3)
    
    # Bottom recommendation
    ax.text(8, 0.5, 'Honcho：理解用户长期画像    |    Mem0：精确事实检索',
            fontsize=13, color=GRAY, ha='center', va='center', style='italic')
    
    plt.tight_layout(pad=0)
    path = os.path.join(OUTPUT_DIR, '03-记忆与知识系统·Provider对比矩阵_04.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
    plt.close(fig)
    print(f'Generated: {path}')


# ============================================================
# Image 5: Knowledge conversion pipeline
# ============================================================
def generate_knowledge_pipeline():
    fig, ax = setup_figure()
    
    ax.text(8, 8.5, '知识转化流水线', fontsize=28, fontweight='bold',
            color=BLACK, ha='center', va='center')
    ax.text(8, 7.8, 'Memory（声明性）→ Skill（过程性）→ Curator（自主维护）', 
            fontsize=14, color=GRAY, ha='center', va='center')
    
    # Three main stages
    stages = [
        (1.5, 4.0, 'Memory\n声明性知识', 'MEMORY.md / USER.md\nProvider 提取的事实\n记录"用户是什么"', YELLOW),
        (6.0, 4.0, 'Skill\n过程性知识', 'SKILL.md 文件\nReview Fork 审视转化\n记录"怎么做某事"', '#E8C547'),
        (10.5, 4.0, 'Curator\n自主维护', '7天周期审查\n评分 → 合并 → 清理\n知识库自我打理', '#D4A017'),
    ]
    
    for x, y, title, desc, color in stages:
        draw_hand_box(ax, x, y, 3.5, 3.5, color=color, fill=color, lw=2.5)
        ax.text(x + 1.75, y + 2.5, title, fontsize=18, fontweight='bold',
                color=BLACK, ha='center', va='center')
        # Split description into lines
        lines = desc.split('\n')
        for j, line in enumerate(lines):
            ax.text(x + 1.75, y + 1.5 - j * 0.5, line, fontsize=11, color=BLACK, 
                    ha='center', va='center')
    
    # Arrows between stages
    draw_hand_arrow(ax, 5.0, 5.75, 5.5, 5.75, color=BLACK, lw=3)
    draw_hand_arrow(ax, 9.5, 5.75, 10.0, 5.75, color=BLACK, lw=3)
    
    # Arrow labels
    ax.text(5.25, 6.3, 'Review Fork', fontsize=11, color=RED, ha='center', va='center')
    ax.text(9.75, 6.3, '周期触发', fontsize=11, color=RED, ha='center', va='center')
    
    # Review Fork detail box
    draw_hand_box(ax, 4.0, 1.2, 8.0, 2.2, color=YELLOW, fill=YELLOW_LIGHT, lw=2)
    ax.text(8, 2.8, 'Review Fork：知识转化的关键触发点', fontsize=14, fontweight='bold',
            color=BLACK, ha='center', va='center')
    ax.text(8, 2.1, '每轮对话后 fork 子 Agent → 受限工具集 → rubric 评分决策',
            fontsize=11, color=BLACK, ha='center', va='center')
    ax.text(8, 1.5, 'relevance · completeness · correctness · actionability',
            fontsize=11, color=GRAY, ha='center', va='center', style='italic')
    
    plt.tight_layout(pad=0)
    path = os.path.join(OUTPUT_DIR, '03-记忆与知识系统·知识转化流水线_05.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
    plt.close(fig)
    print(f'Generated: {path}')


# ============================================================
# Image 6: Skill lifecycle state machine
# ============================================================
def generate_skill_lifecycle():
    fig, ax = setup_figure()
    
    ax.text(8, 8.5, 'Skill 生命周期状态机', fontsize=28, fontweight='bold',
            color=BLACK, ha='center', va='center')
    ax.text(8, 7.8, '从创建到归档的六状态完整闭环', fontsize=14, color=GRAY, ha='center', va='center')
    
    # State positions
    states = [
        (2.0, 5.0, 'created', '创建', YELLOW, 'Agent 通过\nskill_manage 创建'),
        (5.5, 5.0, 'used', '使用', '#E8C547', '被 Agent\n加载使用'),
        (9.0, 5.5, 'graded', '评分', '#D4A017', 'Review Fork\nrubric 打分'),
        (9.0, 3.0, 'improved', '改进', '#C8960C', 'Agent 主动\n或 Fork 建议改进'),
        (5.5, 2.0, 'consolidated', '合并', GREEN, '归入伞技能\n内容保留'),
        (2.0, 2.0, 'archived', '归档', GRAY, '暂不需要\n可恢复'),
    ]
    
    for x, y, name, chinese, color, desc in states:
        draw_hand_box(ax, x, y, 2.5, 1.8, color=color, fill=color, lw=2)
        ax.text(x + 1.25, y + 1.1, chinese, fontsize=16, fontweight='bold',
                color=BLACK, ha='center', va='center')
        ax.text(x + 1.25, y + 0.1, desc, fontsize=9, color=BLACK, ha='center', va='center')
    
    # State transitions (arrows)
    # created -> used
    draw_hand_arrow(ax, 4.5, 5.9, 5.0, 5.9, color=BLACK, lw=2)
    # used -> graded
    draw_hand_arrow(ax, 8.0, 5.9, 8.5, 5.9, color=BLACK, lw=2)
    # used -> improved
    draw_hand_arrow(ax, 8.0, 4.6, 8.5, 4.1, color=BLACK, lw=2)
    # graded -> improved  
    draw_hand_arrow(ax, 9.0, 4.8, 9.0, 4.7, color=BLACK, lw=2)
    # graded -> consolidated
    draw_hand_arrow(ax, 8.3, 4.8, 6.8, 3.0, color=GREEN, lw=2)
    # improved -> consolidated
    draw_hand_arrow(ax, 8.3, 3.0, 6.8, 2.7, color=GREEN, lw=2)
    # consolidated -> archived
    draw_hand_arrow(ax, 4.5, 2.7, 4.0, 2.7, color=GRAY, lw=2)
    
    # Labels
    ax.text(4.75, 6.2, '加载', fontsize=10, color=GRAY, ha='center')
    ax.text(8.25, 6.2, '审视', fontsize=10, color=GRAY, ha='center')
    ax.text(8.25, 4.35, '改进', fontsize=10, color=GRAY, ha='center')
    ax.text(7.5, 3.9, '合并', fontsize=10, color=GREEN, ha='center')
    ax.text(7.5, 3.1, '合并', fontsize=10, color=GREEN, ha='center')
    ax.text(4.25, 3.0, '归档', fontsize=10, color=GRAY, ha='center')
    
    # agentskills.io badge
    ax.text(8, 0.6, '基于 agentskills.io 开放标准 · YAML frontmatter 声明元数据',
            fontsize=11, color=GRAY, ha='center', va='center', style='italic')
    
    plt.tight_layout(pad=0)
    path = os.path.join(OUTPUT_DIR, '03-记忆与知识系统·Skill生命周期_06.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
    plt.close(fig)
    print(f'Generated: {path}')


# ============================================================
# Image 7: Curator review process
# ============================================================
def generate_curator_process():
    fig, ax = setup_figure()
    
    ax.text(8, 8.5, 'Curator 自主审查流程', fontsize=28, fontweight='bold',
            color=BLACK, ha='center', va='center')
    ax.text(8, 7.8, '7天周期 · 全库扫描 · 三层分类信号 · 七道安全防线', 
            fontsize=14, color=GRAY, ha='center', va='center')
    
    # Flow steps
    steps = [
        (1.0, 5.5, '① 定时触发', 'Gateway Cron\n≥ 7天 + 空闲2h'),
        (3.5, 5.5, '② 自动状态转换', '标记 stale\n纯规则，不调 LLM'),
        (6.0, 5.5, '③ LLM 审查', 'umbrella-first\n9999次迭代上限'),
        (8.5, 5.5, '④ 评分决策', '合并 vs 清理\n三层信号判定'),
        (11.0, 5.5, '⑤ 执行 + 报告', '快照备份\nREPORT.md 输出'),
    ]
    
    for x, y, title, desc in steps:
        draw_hand_box(ax, x, y, 2.2, 2.5, color=YELLOW, fill=YELLOW_LIGHT, lw=2)
        ax.text(x + 1.1, y + 1.8, title, fontsize=13, fontweight='bold',
                color=BLACK, ha='center', va='center')
        lines = desc.split('\n')
        for j, line in enumerate(lines):
            ax.text(x + 1.1, y + 1.0 - j * 0.45, line, fontsize=9.5, color=BLACK,
                    ha='center', va='center')
    
    # Connecting arrows
    for i in range(4):
        x1 = 1.0 + i * 2.5 + 2.2
        x2 = x1 + 0.3
        draw_hand_arrow(ax, x1, 6.75, x2, 6.75, color=YELLOW, lw=2)
    
    # Three-layer classification signal
    ax.text(8, 3.8, '三层分类信号（优先级递减）', fontsize=15, fontweight='bold',
            color=BLACK, ha='center', va='center')
    
    signal_boxes = [
        (1.5, 1.8, 3.5, '第一层\nabsorbed_into 参数', 'Agent 声明式\n最权威信号'),
        (5.5, 1.8, 3.5, '第二层\nYAML 结构化摘要', 'LLM 输出\nfenced YAML 块'),
        (9.5, 1.8, 3.5, '第三层\n工具调用证据', '启发式扫描\nskill_manage 引用'),
    ]
    
    for x, y, w, title, desc in signal_boxes:
        color = YELLOW if x < 4 else ('#E8C547' if x < 8 else '#D4A017')
        draw_hand_box(ax, x, y, w, 1.6, color=color, fill=color, lw=2)
        ax.text(x + w/2, y + 0.9, title, fontsize=12, fontweight='bold',
                color=BLACK, ha='center', va='center')
        ax.text(x + w/2, y + 0.2, desc, fontsize=9.5, color=BLACK, ha='center', va='center')
    
    # Priority arrows
    draw_hand_arrow(ax, 5.0, 2.6, 5.0, 2.3, color=RED, lw=1.5)
    draw_hand_arrow(ax, 9.0, 2.6, 9.0, 2.3, color=RED, lw=1.5)
    
    # Safety note
    ax.text(8, 0.4, '防御纵深：bundled/hub/pinned 只读 · 归档可恢复 · 永不自删 · 快照回滚',
            fontsize=10, color=RED, ha='center', va='center', style='italic')
    
    plt.tight_layout(pad=0)
    path = os.path.join(OUTPUT_DIR, '03-记忆与知识系统·Curator审查流程_07.png')
    fig.savefig(path, dpi=150, bbox_inches='tight', facecolor=WHITE, edgecolor='none')
    plt.close(fig)
    print(f'Generated: {path}')


# ============================================================
# Main
# ============================================================
if __name__ == '__main__':
    np.random.seed(42)
    print(f'Output directory: {OUTPUT_DIR}')
    generate_cover()
    generate_architecture_overview()
    generate_provider_lifecycle()
    generate_provider_comparison()
    generate_knowledge_pipeline()
    generate_skill_lifecycle()
    generate_curator_process()
    print('\nAll 7 images generated successfully!')
