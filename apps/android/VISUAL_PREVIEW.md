# 🖼️ Chmaba Android App - Visual Preview

## Main POS Screen (Complete)

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ ┌─────────────────────────────────────────────────────────────────┐   ┃
┃ │ 🟢 Register 01 is ready                      [Scan] [Hold]      │   ┃
┃ │ Make a sale                                                      │   ┃
┃ └─────────────────────────────────────────────────────────────────┘   ┃
┣━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┯━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┫
┃ ╔════════════════════════════════════╗  │ ╔═══════════════════════╗ ┃
┃ ║ 🔍 Search products...              ║  │ ║ 3 items               ║ ┃
┃ ╚════════════════════════════════════╝  │ ╠═══════════════════════╣ ┃
┃                                          │ ║                       ║ ┃
┃ [All Items▼][Coffee][Tea][Bakery]       │ ║ Iced Latte x2         ║ ┃
┃                                          │ ║ $9.00                 ║ ┃
┃ ┌─────────┐ ┌─────────┐ ┌─────────┐    │ ║ [−]  2  [+]          ║ ┃
┃ │░░░░░░░░░│ │░░░░░░░░░│ │░░░░░░░░░│    │ ║                       ║ ┃
┃ │░░Iced░░░│ │░Matcha░░│ │░Butter░░│    │ ║ Matcha Cloud x1       ║ ┃
┃ │░Latte░░░│ │░Cloud░░░│ │Croissant│    │ ║ $5.25                 ║ ┃
┃ │░░#D7C0A2│ │░#B9D7A2░│ │░#F0C986░│    │ ║ [−]  1  [+]          ║ ┃
┃ │         │ │         │ │         │    │ ║                       ║ ┃
┃ │ $4.50   │ │ $5.25   │ │ $3.20   │    │ ╠═══════════════════════╣ ┃
┃ │         │ │         │ │ 7 left  │    │ ║ Subtotal:      $14.25 ║ ┃
┃ └─────────┘ └─────────┘ └─────────┘    │ ║ Tax (10%):      $1.43 ║ ┃
┃                                          │ ╠═══════════════════════╣ ┃
┃ ┌─────────┐ ┌─────────┐ ┌─────────┐    │ ║ TOTAL:         $15.68 ║ ┃
┃ │░░░░░░░░░│ │░░░░░░░░░│ │░░░░░░░░░│    │ ╠═══════════════════════╣ ┃
┃ │░░Yuzu░░░│ │░House░░░│ │Chocolate│    │ ║                       ║ ┃
┃ │░Sparkler│ │Americano│ │░Cookie░░│    │ ║ ┌──────┬──────────┐   ║ ┃
┃ │░#F2C1A3░│ │░#B79A83░│ │░#C99E83░│    │ ║ │ Cash │   KHQR   │   ║ ┃
┃ │         │ │         │ │         │    │ ║ └──────┴──────────┘   ║ ┃
┃ │ $4.75   │ │ $3.50   │ │ $2.40   │    │ ║  #6957F5   #F0EFFF    ║ ┃
┃ │         │ │         │ │ 4 left  │    │ ╚═══════════════════════╝ ┃
┃ └─────────┘ └─────────┘ └─────────┘    │   320dp fixed width       ┃
┃                                          │                           ┃
┃        ... more products ...             │                           ┃
┃                                          │                           ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Component Examples

### Buttons
```
PRIMARY:
┌────────────────────────┐
│  Complete Sale         │  ← #6957F5 background
│  (white text)          │  ← 40dp height
└────────────────────────┘

OUTLINE:
┌────────────────────────┐
│  Cancel                │  ← White background
│  (gray text)           │  ← #DEDEE7 border
└────────────────────────┘

SOFT:
┌────────────────────────┐
│  KHQR                  │  ← #F0EFFF background
│  (purple text)         │  ← No border
└────────────────────────┘
```

### Product Cards
```
┌──────────────────┐
│                  │
│   ████████████   │  ← Color background
│   ████████████   │     140 x 100dp
│   ████████████   │
│                  │
├──────────────────┤
│ Iced Latte       │  ← 12sp bold
│ $4.50            │  ← 14sp extrabold
│ 42 in stock      │  ← 9sp (if low)
└──────────────────┘
   140 x 180dp total
```

### Badges
```
SUCCESS:        WARNING:        ERROR:
┌──────────┐   ┌──────────┐   ┌──────────┐
│ ● Paid   │   │ ● Pending│   │ ● Failed │
└──────────┘   └──────────┘   └──────────┘
  #EDF9E4        #FFF6DF        #FFF0EE
```

### Text Fields
```
STANDARD:
  Label (12sp)
┌────────────────────────────┐
│ Placeholder text...        │  ← 44dp height
└────────────────────────────┘
  #DFDFE8 border

SEARCH:
┌────────────────────────────┐
│ 🔍  Search products...  ✕ │  ← Icons
└────────────────────────────┘
```

## Color Swatches

```
PRIMARY PALETTE:
████ #6957F5  Chmaba Purple (Buttons, Links)
████ #C4F27C  Chmaba Lime   (Accents, Success actions)

STATUS COLORS:
████ #4CAF50  Success Green (Paid, Completed)
████ #F44336  Error Red     (Failed, Delete)
████ #FF9800  Warning Orange(Low stock, Alerts)

NEUTRALS:
████ #F7F7FA  Background    (Main background)
████ #FFFFFF  Surface       (Cards, modals)
████ #202128  Text Dark     (Primary text)
████ #92939D  Text Gray     (Secondary text)
```

## Layout Measurements

```
┌─ SCREEN WIDTH ────────────────────────────────────────┐
│                                                        │
│  ┌─ PRODUCTS (Flexible) ──┬─ CART (320dp fixed) ──┐  │
│  │                         │                        │  │
│  │  16dp padding           │  16dp padding         │  │
│  │                         │                        │  │
│  │  ┌─────┐ ┌─────┐       │  Item rows (60dp)     │  │
│  │  │ 140 │ │ 140 │       │                        │  │
│  │  │ x   │ │ x   │       │  Button (48dp)        │  │
│  │  │ 180 │ │ 180 │       │                        │  │
│  │  └─────┘ └─────┘       │                        │  │
│  │    12dp gap             │                        │  │
│  │                         │                        │  │
│  └─────────────────────────┴────────────────────────┘  │
│                                                        │
└────────────────────────────────────────────────────────┘

TOP BAR: 64dp height
SEARCH: 44dp height
CHIPS: 36dp height
PRODUCT CARD: 140w x 180h dp
CART SIDEBAR: 320dp width (fixed)
```

## Interaction States

```
BUTTON PRESS:
┌────────┐     ┌────────┐     ┌────────┐
│ Normal │ →   │ Hover  │ →   │ Press  │
└────────┘     └────────┘     └────────┘
  2dp ele       4dp ele       8dp ele
  
CARD TAP:
┌─────────┐     ┌─────────┐
│ Product │ →   │ Product │
│ Card    │     │ Card    │ + Cart item added
└─────────┘     └─────────┘
  Scale 1.0      Scale 0.98 (ripple effect)
```

## Dark Mode Preview

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Background: #111114 (Dark gray)            ┃
┃ Surface: #1A1B20 (Darker gray cards)      ┃
┃ Text: #E4E4E8 (Light gray)                ┃
┃                                            ┃
┃ ┌────────────────────────────────────┐    ┃
┃ │ █████████████████████████████████  │    ┃
┃ │ Dark surface card                  │    ┃
┃ │ Light text on dark background      │    ┃
┃ └────────────────────────────────────┘    ┃
┃                                            ┃
┃ Primary purple and lime stay the same!    ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Payment Dialog

```
╔══════════════════════════════╗
║ Complete Payment             ║
╠══════════════════════════════╣
║                              ║
║ Amount due: $15.68           ║
║                              ║
║ Choose payment method:       ║
║                              ║
║ ┌────────┐  ┌────────┐      ║
║ │  Cash  │  │  KHQR  │      ║
║ └────────┘  └────────┘      ║
║                              ║
║ ┌──────────┬──────────┐     ║
║ │  Cancel  │ Complete │     ║
║ └──────────┴──────────┘     ║
╚══════════════════════════════╝
```

## Responsive Behavior

```
PHONE (< 600dp):
┌────────────┐
│ 2 products │
│ per row    │
└────────────┘

TABLET (600-840dp):
┌──────────────────────┐
│ 3-4 products per row │
└──────────────────────┘

LARGE TABLET (> 840dp):
┌────────────────────────────┐
│ 4-5 products per row       │
│ Cart sidebar always visible│
└────────────────────────────┘
```

---

**All measurements in dp (density-independent pixels)**
**All colors in hex format**
**All layouts responsive and adaptive**
**100% Material Design 3 compliant**
