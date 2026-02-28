# Urban Memory Layer

**A prototype spatial narrative engine for adaptive, multi-layered urban storytelling.**

This project explores how cities can function as structured, walkable memory systems — where the same place can be interpreted through multiple narrative layers and visitor depths, without rewriting content.

🔗 **Live Demo:** [(https://urban-memory-layer-bo5tmkpdridp645s9d8inz.streamlit.app/)]

---

## What this prototype demonstrates

### 1. Layered Interpretation
Each location is modeled as a reusable narrative node and can be viewed through:
- Economic
- Social
- Political
- Spatial
- Institutional lenses

The same route can be reinterpreted dynamically through different cultural logics.

---

### 2. Adaptive Narrative Depth
Every stop contains three narrative outputs:
- **Explorer** — concise highlight
- **Deep Dive** — contextual framing
- **Behind the Scenes** — institutional / systems perspective

Depth adapts to visitor preference without duplicating data.

---

### 3. Spatial Narrative Infrastructure
- Route-based sequencing
- Map visualization with density layer (memory concentration within ~250m)
- Optional audio moments (multi-modal storytelling)

The system models cultural memory as a structured, queryable layer — not just a static guided tour.

---

## Why this matters

Heritage platforms often duplicate stories across routes, audiences, and thematic categories.

This prototype explores a scalable alternative:

**Store once. Interpret dynamically. Compose experiences adaptively.**

---

## Future Directions

This prototype establishes narrative infrastructure.  
Possible evolutions include:

### Historical Persona Mode
Visitors encounter first-person narratives from historical figures connected to each location — shifting interpretation from *about history* to *inside history*.

### Dynamic Route Recomposition
Auto-generated routes based on:
- Time available
- Visitor interest profile
- Current location
- Spatial density patterns

### Multi-Voice Memory Layers
Toggle between:
- Institutional narratives
- Community memory
- Counter-histories
- Academic interpretations

### Real-Time Contextual Triggers
Stories activate based on:
- Time of day
- Anniversaries
- Proximity clusters
- Visitor movement patterns

---

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
