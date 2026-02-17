# Modo: Technical Minimalism & Dot-Matrix Design System

## 1. Core Identity: "Digital Noir"
The objective is to replace all standard software tropes with a high-fidelity hardware aesthetic. Every visual element must look like it belongs on a specialized physical device or a high-end terminal workstation.

### Mandatory Constraints
* **Typography**: Strictly **Monospaced** or **Dot-Matrix** fonts only.
* **Architecture**: No rounded corners (max 2px), no drop shadows, and no transparency unless used for dithered effects.
* **Borders**: 1px solid lines only.

---

## 2. Multi-Mode Canvas Logic
The system must dynamically map to the user's existing mode (Light, Dark, or AMOLED) while using the **User Accent Color** as the primary signal.

* **Light Mode**: Background: `#F2F2F2` | Text/Borders: Deep Charcoal.
* **Dark Mode**: Background: `#121212` | Text/Borders: Off-White.
* **AMOLED Mode**: Background: `#000000` | Text/Borders: Pure White.

---

## 3. The Dot-Matrix Components
All "filling" or "sliding" UI elements are deprecated in favor of discrete hardware-inspired arrays.

### A. Progress Arrays (The Progress Bar)
* **Structure**: A 1x10 or 1x20 row of 6px dots.
* **Active State**: Solid fill using `--user-accent` with a subtle 4px bloom.
* **Inactive State**: 1px stroke of `--user-accent` at 10% opacity.
* **Animation**: Dots must "flip" or "light up" instantly; no smooth transitions.

### B. The CRT Halftone Aura
* **Concept**: A radial "glow" surrounding the timer readout.
* **Execution**: Instead of a gradient, use a **Halftone Mask**—a pattern of dots that decreases in size as they move away from the center.
* **Color**: Pulses in the `--user-accent` color during active sessions.

### C. Digital Clock Readout
* **Font**: 7x9 bitmapped glyphs.
* **Color**: Always rendered in the solid `--user-accent` color.

---

## 4. Input & Interactive Logic
* **Buttons**: Solid rectangular blocks of `--user-accent` with labels knocked out in the background color.
* **Inputs**: Command-line prompts with a blinking block cursor `█` in the accent color.
* **Grid**: A stationary 24px radial dot-grid background that grounds all components.

---

## 5. CLI Implementation Directive
"You are the Lead UI Architect for Modo. Purge all standard 'SaaS' design choices. Every component must be a derivative of a dot-matrix grid. Strictly integrate the user's **Settings > Accent Color** into all progress indicators, timers, and buttons. Whether the user is in Light, Dark, or AMOLED mode, the Digital Noir structure must remain absolute."
