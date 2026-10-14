# Chmaba POS · Android — Motion Specification

Every animation is defined here before it is written in Compose. Nothing is
invented per screen: screens use **shared tokens** so motion feels like one product.

## 1. Motion tokens

| Token | Value | Use |
|---|---|---|
| `motion.fast` | 120 ms | press / release feedback |
| `motion.base` | 180 ms | colour, border, focus changes |
| `motion.enter` | 300 ms | lists, tiles, sheets |
| `motion.hero` | 340 ms | headings and card enters |
| `motion.slow` | 550 ms | charts, progress fills |
| `motion.ambient` | 1500 ms | splash staging |
| `ease.standard` | `cubic-bezier(.2,.8,.3,1)` | enters |
| `ease.emphasised` | `cubic-bezier(.2,.9,.3,1)` | sheets, tiles |
| `ease.spring` | `cubic-bezier(.2,.9,.3,1.2)` | pop (icons, ticks) |
| `stagger.step` | 30–40 ms | per-item delay, capped at 6 items |

**Rule:** max one *ambient* (looping) animation visible per screen. Everything else
is one-shot. All motion is disabled under `prefers-reduced-motion` / Android's
"Remove animations" setting.

## 2. Global behaviour

| Element | Animation | Notes |
|---|---|---|
| Screen change | fade-in 220 ms + children stagger up 10px | replaces platform slide for in-app navigation |
| Back navigation | reverse stagger, no fade | feels like returning, not restarting |
| Bottom nav tap | icon pop 250 ms + active pill slide | pill moves between tabs, 200 ms |
| App bar | border + shadow fade in on scroll | already in prototype |
| Toast | slide up 200 ms, auto-dismiss 3 s | shop floor messages |

## 3. Per-screen specification

### A. Boot & Auth
| Screen | Animation |
|---|---|
| **Splash 1** | brandmark scale .86→1 with spring, 600 ms; wordmark fade-up 120 ms later |
| **Splash 2** | kicker fade-up, heading fade-up +40 ms, 3 feature icons pop in staggered 80 ms |
| **Splash 3** | progress bar loops 1.9 s (indeterminate); label pulse-soft 2.3 s; advances after 1.5 s |
| **Login / Signup** | hero heading fade-up 60 ms; sheet rises 18px with the card; Google button last in stagger |
| **Input focus** | border → purple 180 ms + 4px ring fade-in; label unchanged (no float) |
| **Email invalid** | shake 380 ms then red border (one-shot, never loops) |
| **Password eye** | icon cross-fade 150 ms between eye / eye-off |
| **Primary CTA** | sheen sweep loops every 3.4 s until tapped; press scale .975 |
| **Google button** | press tint 160 ms; on tap, spinner replaces the G, 24px → 18px fade |
| **Verify · OTP** | each box pops 250 ms on fill; auto-advance focus ring slides right |
| **Verify · Gmail** | dashed border pulses once when the code is found |
| **Reset password** | key-icon card fades up; strength hint colour-animates as it improves |
| **Access denied** | lock card fades up; the 3 "what happens next" rows stagger 60 ms; shield button sheen |

### B. Onboarding
| Screen | Animation |
|---|---|
| **Setup · progress** | bar width eases 300 ms per step; step badge cross-fades |
| **Setup · Company** | fields stagger 40 ms; country select opens with platform picker |
| **Setup · Questions** | cards stagger 40 ms; selection ring eases 180 ms; tick pops with spring |
| **Setup · Plan** | cycle rows stagger; selecting a row slides the radio dot 160 ms; choosing a card lifts it 2px + ring; CTA label cross-fades |
| **Setup · Ready** | party icon pop-spring; two CTAs stagger |

### C. Core app
| Screen | Animation |
|---|---|
| **Dashboard** | 4 metric cards stagger 50 ms; chart bars grow 550 ms with 50 ms offset each; top-product tracks fill 600 ms; recent rows cascade 40 ms |
| **POS · grid** | tiles pop in staggered 30 ms (cap 6); scroll is free |
| **POS · add item** | tile scales .97 then releases; cart badge count pops; cart FAB nudges 2px |
| **POS · cart sheet** | sheet rises 300 ms with scrim fade 220 ms; on add, the new line fades in and the total ticks up |
| **POS · quantity** | number cross-fades 120 ms; row height animates if a line is removed |
| **Modifier / Combo** | sheet rises; option cards stagger; selected option ring eases; total text cross-fades |
| **Payment sheet** | sheet rises; Cash/KHQR tiles stagger; change-due number counts up 250 ms |
| **KHQR** | QR scales in 300 ms; status badge pulses softly while pending; switches to a green check with spring on success |
| **Receipt** | paper slides up 320 ms; success banner fades in; print button sheen |
| **Orders** | stat row staggers; filter chips slide-underline; rows cascade |
| **Order detail** | items fade in; totals count up; refund button shakes once on confirm |
| **Products** | rows cascade; toggle switch animates 180 ms |
| **Product editor** | sections stagger; image picker cross-fades thumbnail; tag chips pop on add |
| **Categories** | tree rows cascade; expand/collapse rotates the chevron 200 ms |
| **Inventory** | stock badges cross-fade colour when the level changes |
| **Purchasing** | PO rows cascade; receiving a line ticks then fades the row |
| **Reports** | metric cards stagger; bars grow staggered; payment breakdown tracks fill |

### D. Account & admin
| Screen | Animation |
|---|---|
| **Suppliers / Team** | rows cascade; invite sheet rises; avatar upload pops |
| **Activity** | feed cascades newest-first; new entry slides in from the top |
| **Billing** | current-plan card lifts on select; cycle rows slide radio; invoice rows cascade |
| **Settings** | section accordions animate height 250 ms; toggles 180 ms; theme switch cross-fades the whole surface 220 ms |
| **Help** | cards cascade; AI card sheen; chat sheet rises |

### E. Surfaces
| Screen | Animation |
|---|---|
| **Customer display** | totals cross-fade on change; QR scales in; PAID state flashes brand green once |
| **Sheets (all)** | rise 300 ms, grab handle; dismiss = reverse 220 ms with scrim fade |
| **Modals/confirm** | scrim fade 200 ms + dialog scale .96→1 |

## 4. Component-level rules

| Component | Animation |
|---|---|
| Button (primary) | press scale .975 (120 ms); optional sheen loop |
| Button (outline/soft) | press tint + scale .975 |
| Icon button | press scale .90, 120 ms with spring |
| Chip / filter | press scale .96; selection eases background 180 ms |
| Card / tile | press scale .97; elevation rises 2dp |
| Input | focus ring 180 ms; error shake once; helper text fades in |
| Checkbox / radio / switch | 180 ms with platform-standard easing |
| Badge | cross-fade when the tone changes |
| Progress / track | width eases 600 ms |
| Skeleton | shimmer sweep 1.2 s while loading (never on cached data) |

## 5. Compose mapping

| Spec | Compose |
|---|---|
| `stagger` enters | `AnimatedVisibility` + `tween(delayMillis = i * 30)` |
| sheet rise | `ModalBottomSheet` default + custom scrim fade |
| press scale | `Modifier.graphicsLayer{scaleX/Y}` in `interactionSource.collectIsPressedAsState()` |
| bar growth | `animateFloatAsState` driving `scaleY` |
| number count-up | `animateIntAsState` + formatted text |
| theme cross-fade | `Crossfade` around the theme wrapper |
| splash staging | `LaunchedEffect` + `delay(1500)` per stage |
| reduced motion | read `Settings.Global.ANIMATOR_DURATION_SCALE`; if 0, set all durations to 0 |

## 6. Non-negotiables

- No animation longer than 600 ms except ambient loops.
- No animation on scrolling lists beyond the initial cascade.
- Sales-critical screens (POS, payment) never block input on motion.
- Every animation must be interruptible by user input.
