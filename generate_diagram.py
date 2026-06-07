"""
Generate a clean node-based architecture diagram for the AI Supply Chain Assistant.
Output: architecture_diagram.png
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import matplotlib.patheffects as pe

fig, ax = plt.subplots(figsize=(16, 22))
ax.set_xlim(0, 16)
ax.set_ylim(0, 22)
ax.axis('off')
fig.patch.set_facecolor('#0D1B2A')
ax.set_facecolor('#0D1B2A')

# ── Colours ───────────────────────────────────────────────────────────────────
C = {
    'node_bg':    '#162838',
    'node_line':  '#00B4D8',
    'text':       '#FFFFFF',
    'sub_text':   '#B0C4D8',
    'arrow':      '#00B4D8',
    'amber':      '#F7B731',
    'red':        '#EF474A',
    'green':      '#2DC65C',
    'purple':     '#AA77FF',
    'cyan_light': '#90E0EF',
    'card_bg':    '#1A2E44',
    'lane_bg':    '#101E2D',
}


# ── Drawing helpers ───────────────────────────────────────────────────────────

def node(ax, x, y, w, h, label, sublabel='', icon='', color=C['node_line'],
         bg=C['node_bg'], fontsize=11, sublabel_size=8.5):
    box = FancyBboxPatch((x - w/2, y - h/2), w, h,
                         boxstyle="round,pad=0.08",
                         linewidth=2, edgecolor=color, facecolor=bg, zorder=3)
    ax.add_patch(box)
    full_label = f"{icon}  {label}" if icon else label
    ax.text(x, y + (0.12 if sublabel else 0), full_label,
            ha='center', va='center', fontsize=fontsize, fontweight='bold',
            color=C['text'], zorder=4)
    if sublabel:
        ax.text(x, y - 0.28, sublabel,
                ha='center', va='center', fontsize=sublabel_size,
                color=C['sub_text'], zorder=4, style='italic')


def agent_node(ax, x, y, w, h, label, sublabel='', color=C['green']):
    node(ax, x, y, w, h, label, sublabel, color=color, bg=C['lane_bg'],
         fontsize=9.5, sublabel_size=8)


def arrow(ax, x1, y1, x2, y2, color=C['arrow'], lw=1.8, label='',
          label_color=C['sub_text'], connectionstyle="arc3,rad=0.0"):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                connectionstyle=connectionstyle),
                zorder=5)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.15, my, label, fontsize=8, color=label_color,
                va='center', style='italic', zorder=6)


def dashed_arrow(ax, x1, y1, x2, y2, color=C['amber'], lw=1.5, label=''):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                linestyle='dashed',
                                connectionstyle="arc3,rad=0.0"),
                zorder=5)
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.15, my, label, fontsize=8, color=color,
                va='center', style='italic', zorder=6)


def lane_box(ax, x, y, w, h, label, color):
    rect = FancyBboxPatch((x, y), w, h,
                          boxstyle="round,pad=0.05",
                          linewidth=1, edgecolor=color,
                          facecolor=C['lane_bg'], alpha=0.35, zorder=1)
    ax.add_patch(rect)
    ax.text(x + 0.18, y + h - 0.22, label, fontsize=8, color=color,
            fontweight='bold', va='top', zorder=2, alpha=0.85)


# ── Title ─────────────────────────────────────────────────────────────────────
ax.text(8, 21.4, 'AI Supply Chain Assistant — Node Architecture',
        ha='center', va='center', fontsize=17, fontweight='bold',
        color='#00B4D8')
ax.text(8, 21.0, 'LangGraph State Machine  ·  9 Nodes  ·  3 Specialist Agents',
        ha='center', va='center', fontsize=10, color=C['sub_text'], style='italic')

# ── Lane backgrounds ──────────────────────────────────────────────────────────
# User
lane_box(ax, 0.4, 19.5, 15.2, 1.15, 'USER', C['cyan_light'])
# Pipeline
lane_box(ax, 0.4, 4.8, 15.2, 14.55, 'LANGGRAPH PIPELINE', C['node_line'])
# Orchestrator sub-lane
lane_box(ax, 3.0, 7.1, 10.0, 4.45, 'ORCHESTRATOR  —  Specialist Agents', C['purple'])
# Data layer
lane_box(ax, 0.4, 0.3, 15.2, 4.3, 'DATA LAYER', C['amber'])

# ── User lane nodes ───────────────────────────────────────────────────────────
node(ax, 3.5, 20.15, 2.6, 0.72, 'React Frontend', 'Chat UI · Agent Trace · Dashboards',
     color=C['cyan_light'], fontsize=10)

node(ax, 8.0, 20.15, 2.6, 0.72, 'FastAPI  /query', 'POST {query, filters, top_k}',
     color=C['cyan_light'], fontsize=10)

arrow(ax, 4.8, 20.15, 6.7, 20.15, label='HTTP POST')
arrow(ax, 9.3, 20.15, 12.0, 20.15, color=C['green'], label='JSON Response')

node(ax, 13.5, 20.15, 2.4, 0.72, 'Evaluation Runner', 'Faithfulness · Relevance',
     color=C['green'], fontsize=10)

# ── Pipeline nodes (main vertical spine) ─────────────────────────────────────
CX = 8.0   # centre x of main spine

# 1. Input Guardrail
node(ax, CX, 18.8, 3.4, 0.78, 'Input Guardrail', 'Length · PII · Format checks',
     color=C['amber'], fontsize=11)
arrow(ax, CX, 20.15 - 0.36, CX, 18.8 + 0.39)

# 2. General Check
node(ax, CX, 17.5, 3.4, 0.78, 'General Check', 'Supply chain or off-topic?',
     color=C['node_line'], fontsize=11)
arrow(ax, CX, 18.8 - 0.39, CX, 17.5 + 0.39)

# 3. NL→SQL
node(ax, CX, 16.1, 3.4, 0.78, 'NL → SQL Agent', 'Query SQLite · Extract entities',
     color=C['green'], fontsize=11)
arrow(ax, CX, 17.5 - 0.39, CX, 16.1 + 0.39, label='supply chain')

# 4. Specialist Classifier
node(ax, CX, 14.7, 3.4, 0.78, 'Specialist Classifier', 'Pick agents · Write sub-queries',
     color=C['node_line'], fontsize=11)
arrow(ax, CX, 16.1 - 0.39, CX, 14.7 + 0.39)

# 5. Vector Retrieval
node(ax, CX, 13.3, 3.4, 0.78, 'Vector Retrieval', 'ChromaDB + BM25 + Reranker',
     color=C['node_line'], fontsize=11)
arrow(ax, CX, 14.7 - 0.39, CX, 13.3 + 0.39, label='agents needed')

# 6. Orchestrator box already drawn as lane
# Supplier, Shipment, Inventory agents inside
arrow(ax, CX, 13.3 - 0.39, CX, 11.1)  # into orchestrator area

# Agent nodes inside orchestrator lane
agent_node(ax, 4.2,  9.8, 2.8, 2.4,
           'Supplier Risk\nAgent',
           'Defect rates · Lead time\nReliability · Risk tier',
           color=C['red'])

agent_node(ax, 8.0,  9.8, 2.8, 2.4,
           'Shipment\nAgent',
           'Delays · Carriers\nRoutes · Regions',
           color=C['amber'])

agent_node(ax, 11.8, 9.8, 2.8, 2.4,
           'Inventory\nAgent',
           'Stock levels · Days supply\nStockouts · Warehouses',
           color=C['green'])

# Arrows between agents (context chaining)
arrow(ax, 5.6, 9.8, 6.6, 9.8, color=C['purple'], lw=1.4, label='prior findings')
arrow(ax, 9.4, 9.8, 10.4, 9.8, color=C['purple'], lw=1.4, label='prior findings')

# Arrow from orchestrator area down
arrow(ax, CX, 8.6, CX, 7.9)

# 7. Summary Node
node(ax, CX, 7.3, 3.4, 0.78, 'Summary Node', 'Synthesise · Anomaly correlation',
     color=C['cyan_light'], fontsize=11)
arrow(ax, CX, 7.9 - 0.09, CX, 7.3 + 0.39)

# 8. Recommendation Engine
node(ax, CX, 5.9, 3.4, 0.78, 'Recommendation Engine', 'Prioritised actions',
     color=C['green'], fontsize=11)
arrow(ax, CX, 7.3 - 0.39, CX, 5.9 + 0.39)

# ── Data layer nodes ──────────────────────────────────────────────────────────
data_y = 2.1
node(ax, 2.4,  data_y, 2.8, 0.8, 'SQLite DB', '5 tables · Structured ops data',
     color=C['green'], bg=C['node_bg'], fontsize=9.5)

node(ax, 5.8,  data_y, 2.8, 0.8, 'ChromaDB', 'Vector embeddings · Profiles',
     color=C['node_line'], bg=C['node_bg'], fontsize=9.5)

node(ax, 9.2,  data_y, 2.8, 0.8, 'BM25 Index', 'Keyword search · Hybrid RAG',
     color=C['cyan_light'], bg=C['node_bg'], fontsize=9.5)

node(ax, 12.6, data_y, 2.8, 0.8, 'LLM Gateway', 'OpenAI API · All agent calls',
     color=C['amber'], bg=C['node_bg'], fontsize=9.5)

# Dotted arrows from pipeline nodes to data stores
ax.annotate('', xy=(2.4, data_y + 0.4), xytext=(7.2, 16.1 - 0.39),
            arrowprops=dict(arrowstyle='->', color=C['green'], lw=1.2,
                            linestyle='dotted', connectionstyle="arc3,rad=0.3"), zorder=5)

ax.annotate('', xy=(5.8, data_y + 0.4), xytext=(7.3, 13.3 - 0.39),
            arrowprops=dict(arrowstyle='->', color=C['node_line'], lw=1.2,
                            linestyle='dotted', connectionstyle="arc3,rad=0.2"), zorder=5)

ax.annotate('', xy=(9.2, data_y + 0.4), xytext=(8.0, 13.3 - 0.39),
            arrowprops=dict(arrowstyle='->', color=C['cyan_light'], lw=1.2,
                            linestyle='dotted', connectionstyle="arc3,rad=-0.1"), zorder=5)

ax.annotate('', xy=(12.6, data_y + 0.4), xytext=(9.2, 9.8),
            arrowprops=dict(arrowstyle='->', color=C['amber'], lw=1.2,
                            linestyle='dotted', connectionstyle="arc3,rad=-0.25"), zorder=5)

# ── Short-circuit / branch paths ──────────────────────────────────────────────

# Guardrail → END (invalid)
node(ax, 13.0, 18.8, 1.6, 0.6, 'END', '', color=C['red'], bg='#2A1010', fontsize=10)
dashed_arrow(ax, 9.7, 18.8, 12.2, 18.8, color=C['red'], label='invalid')

# General check → General QA (off-topic)
node(ax, 13.0, 17.5, 1.9, 0.72, 'General QA', 'BaseAgent · Direct answer',
     color=C['amber'], fontsize=9)
dashed_arrow(ax, 9.7, 17.5, 12.05, 17.5, color=C['amber'], label='off-topic')
arrow(ax, 13.95, 17.5, 14.5, 17.5, color=C['amber'])
node(ax, 15.1, 17.5, 1.0, 0.5, 'END', '', color=C['amber'], bg='#2A1E10', fontsize=9)

# Classifier → skip to recommendation (no agents)
dashed_arrow(ax, 9.7, 14.7, 12.5, 14.7, color=C['amber'])
ax.text(10.3, 14.95, 'SQL sufficient\n(skip agents)', fontsize=7.5,
        color=C['amber'], style='italic', va='center')
ax.annotate('', xy=(12.5, 5.9), xytext=(12.5, 14.7 - 0.39),
            arrowprops=dict(arrowstyle='->', color=C['amber'], lw=1.3,
                            linestyle='dashed', connectionstyle="arc3,rad=0.0"), zorder=5)

# ── Legend ────────────────────────────────────────────────────────────────────
legend_x, legend_y = 0.6, 4.5
items = [
    (C['node_line'], 'Main pipeline node'),
    (C['green'],     'Specialist agent / output'),
    (C['amber'],     'Conditional / branch path'),
    (C['red'],       'Guard / rejection'),
    (C['purple'],    'Context chaining between agents'),
]
ax.text(legend_x, legend_y, 'Legend', fontsize=9, color=C['sub_text'],
        fontweight='bold', va='top')
for i, (col, lbl) in enumerate(items):
    ly = legend_y - 0.32 - i * 0.28
    ax.plot([legend_x, legend_x + 0.35], [ly, ly], color=col, lw=2.5)
    ax.text(legend_x + 0.5, ly, lbl, fontsize=8, color=C['sub_text'], va='center')

# ── Output ────────────────────────────────────────────────────────────────────
out = r'd:\FDE\Repo_Projects\capstone_ai_supply_chain_assistant\architecture_diagram.png'
plt.tight_layout(pad=0)
plt.savefig(out, dpi=180, bbox_inches='tight', facecolor=fig.get_facecolor())
print(f'Saved: {out}')
plt.close()
