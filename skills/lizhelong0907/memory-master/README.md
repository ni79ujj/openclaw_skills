# 🧠 Memory Master v2.5.3

**Local Memory System with Structured Indexing and Auto-Learning**

---

## What is Memory Master?

A memory system for AI agents with **auto-write**, **heuristic recall**, and **auto learning**. Also compatible with self-improving-agent patterns.

### Core Features

- 📝 **Structured Memory**: "Cause → Change → Todo" format
- 🔄 **Auto Index Sync**: Write once, index updates automatically  
- ⚡ **Heuristic Recall**: Proactively finds relevant memories when context is missing
- 🧠 **Auto Learning**: When knowledge is insufficient, automatically search web to learn
- 🎯 **Skill Auto-Record**: When skill completes or errors, automatically record to knowledge base
- 🔒 **100% Local**: All data stored locally, nothing leaves your machine
- 🔓 **Transparent**: All files visible/editable/deletable

---

## What Can It Do?

### 1. Auto-Write Memory
- Automatically records discussions when conclusions are reached
- Records decisions, action items, important events
- No need to remind the AI - it writes automatically

### 2. Heuristic Recall
- When context is missing, proactively searches index to find relevant memories
- No need for user to say "remember" - AI finds it automatically

### 3. Auto Learning
- When knowledge is insufficient, automatically searches the web to learn
- Writes new knowledge to knowledge base for future use

### 4. Skill Auto-Record (Compatible with self-improving-agent)
- When skill completes: records what was learned
- When skill errors: records error and solution
- All written to knowledge base

---

## Directory Structure

```
memory/
├── daily-index.md        # Memory index
├── knowledge-index.md    # Knowledge index  
├── daily/               # Daily memories
│   └── YYYY-MM-DD.md
└── knowledge/           # Knowledge base
    └── *.md
```

---

## Memory Format

```
## [日期] 主题
- 因：原因/背景
- 改：做了什么
- 待：待办
```

---

## Quick Start

```bash
# Install
clawdhub install memory-master

# Initialize (creates directories and copies rules)
# See SKILL.md for detailed instructions
```

---

## Comparison

| Feature | Traditional Memory | Memory Master |
|---------|------------------|---------------|
| Auto-write | ❌ | ✅ |
| Heuristic recall | ❌ | ✅ |
| Auto learning | ❌ | ✅ |
| Skill auto-record | ❌ | ✅ |
| 100% local | ✅ | ✅ |

---

## Rules Summary

- Write automatically when discussion reaches conclusion
- Write automatically when skill completes or errors
- Learn automatically when knowledge is insufficient
- Full user control: all files visible/editable/deletable

---

**Memory Master** — *Remember what matters, forget what doesn't.* 🧠⚡
