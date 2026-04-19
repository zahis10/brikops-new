# BrikOps — Icon Export Package

Final icon: **07.0A Flat** — solid navy `#323A4E` background, flat orange `#EE8E3C` "B" monogram.

## 📁 Folder structure

```
export/
├── ios/                  # iOS AppIcon set (1024 + all sizes)
├── android/              # Adaptive icon (fg + bg layers) + legacy
├── favicon/              # 16 / 32 / 48 + apple-touch-icon
├── pwa/                  # 192 / 512 + maskable variants
├── manifest.json         # PWA web app manifest
└── capacitor.config.ts   # Capacitor bootstrap config
```

## 🍎 iOS

- **`ios/AppIcon-1024.png`** — marketing icon. **No alpha, no rounded corners** — iOS applies the squircle mask at runtime.
- All other sizes (20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180) pre-rendered.
- In Xcode: drop the whole set into `Assets.xcassets/AppIcon.appiconset/` and the Contents.json entries will resolve by size.

## 🤖 Android — Adaptive Icon

Adaptive icons are composed of two layers drawn on a 108 × 108 dp canvas, with the outer 25% on each side reserved for OS mask effects. The safe zone is the central **66% (72 dp)**.

- **`android/ic_launcher_foreground-432.png`** — orange "B" only, transparent background. Sits within the safe zone.
- **`android/ic_launcher_background-432.png`** — solid navy `#323A4E`.
- **`android/ic_launcher_foreground-1024.png`** / **`-1024.png`** — 1024 variants for higher-density sources.
- **`android/ic_launcher-512.png`** — legacy composite (pre-Android 8, Play Store fallback).
- **`android/playstore-icon-512.png`** — Google Play listing icon (512 × 512, no alpha).

### Android Studio setup

```xml
<!-- res/mipmap-anydpi-v26/ic_launcher.xml -->
<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
    <background android:drawable="@mipmap/ic_launcher_background"/>
    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
</adaptive-icon>
```

Or use the background as a solid color:

```xml
<!-- res/values/ic_launcher_background.xml -->
<resources>
    <color name="ic_launcher_background">#323A4E</color>
</resources>
```

## 🌐 Favicon

Designed for readability at browser-tab scale — the "B" is zoomed (~8% margin instead of the ~21% used in the full icon) so it doesn't vanish into a colored square.

- `favicon/favicon-16.png`
- `favicon/favicon-32.png`
- `favicon/favicon-48.png`
- `favicon/apple-touch-icon-180.png`

### HTML

```html
<link rel="icon" type="image/png" sizes="32x32" href="/favicon/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon/favicon-16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/favicon/apple-touch-icon-180.png">
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#323A4E">
```

### Generating a .ico (optional)

```bash
# Combine 16/32/48 into one .ico
convert favicon/favicon-16.png favicon/favicon-32.png favicon/favicon-48.png favicon.ico
```

## 📱 PWA

- `pwa/icon-192.png`, `pwa/icon-512.png` — standard (`purpose: "any"`).
- `pwa/icon-192-maskable.png`, `pwa/icon-512-maskable.png` — maskable variant with inner 80% safe zone, for Android home-screen shortcuts, Chrome OS, etc.

`manifest.json` is already wired up — just copy the icons to `/icons/pwa/` in your `public/` folder (or adjust paths).

## ⚡ Capacitor

`capacitor.config.ts` has the base setup. To regenerate all native icon/splash assets from a single 1024 source:

```bash
npm install -D @capacitor/assets
# Put the high-res source at resources/
#   resources/icon-only.png        (1024×1024)
#   resources/icon-foreground.png  (1024×1024, transparent)
#   resources/icon-background.png  (1024×1024)
#   resources/splash.png           (2732×2732, centered)

npx @capacitor/assets generate --iconBackgroundColor '#323A4E' \
                               --iconBackgroundColorDark '#323A4E' \
                               --splashBackgroundColor '#323A4E' \
                               --splashBackgroundColorDark '#323A4E'
```

`@capacitor/assets` is the modern replacement for `cordova-res`. If you prefer the older tool:

```bash
npm install -g cordova-res
cordova-res ios --skip-config --copy
cordova-res android --skip-config --copy
```

Source images expected at `resources/icon.png` (1024×1024) and `resources/splash.png` (2732×2732).

## 🎨 Brand tokens

```
--brand-navy:   #323A4E;
--brand-orange: #EE8E3C;
```

Use the navy for splash backgrounds, loading states, and dark-mode chrome. Use the orange only for primary calls-to-action and brand accents — never for body text.

## 📝 Notes

- iOS `AppIcon-1024.png` is **opaque** — do not re-export with alpha channel or App Store Connect will reject it.
- Android adaptive foreground must remain **transparent** outside the B; the launcher composites it over the background layer.
- Favicons use a tighter crop intentionally. Do not rebuild them with the full-icon padding — they'll become unreadable at 16 × 16.
- All PNGs are pixel-aligned and pre-rendered from a single SVG path, so they're consistent at every scale.
