# 🚀 Quick Start Guide - Premium Pages

## Activate Premium Pages

The new premium pages are ready in separate files. Here's how to activate them:

### Option 1: Replace Old Pages (Recommended)

**For Scan Page:**
```bash
# Backup the old version
cp frontend/app/scan/page.tsx frontend/app/scan/page.backup.tsx

# Replace with premium version
cp frontend/app/scan/page_new.tsx frontend/app/scan/page.tsx
```

**For Exam Page:**
```bash
# Backup the old version
cp frontend/app/exam/page.tsx frontend/app/exam/page.backup.tsx

# Replace with premium version
cp frontend/app/exam/page_new.tsx frontend/app/exam/page.tsx
```

**For Homepage:**
You can update incrementally since the module data was already updated. The current homepage has the premium data structure. If you want the full premium layout, replace with content from `page_new.tsx`.

### Option 2: Keep Both & Switch with Routes

Add route variants in Next.js:
```tsx
// app/scan/premium/page.tsx
export { default } from "../page_new"

// app/exam/premium/page.tsx  
export { default } from "../page_new"
```

Then access via:
- Premium scan: `/scan/premium`
- Premium exam: `/exam/premium`

---

## Add Header to All Pages

Update `app/layout.tsx` to include the new header:

```tsx
import Header from "@/components/layout/Header"

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        <Header />
        {children}
      </body>
    </html>
  )
}
```

---

## Use Premium Components

### Import Components
```tsx
import { 
  ProgressIndicator, 
  AgentOrchestrator, 
  ScanResultCard, 
  StatsDashboard 
} from "@/components/ui"
```

### Example: Add Progress to Scan Detail Page

**File: `app/scan/[id]/page.tsx`**

```tsx
"use client"

import { useState, useEffect } from "react"
import { ProgressIndicator, AgentOrchestrator } from "@/components/ui"

export default function ScanDetailPage({ params }: { params: { id: string } }) {
  const [progress, setProgress] = useState(0)
  const [agents, setAgents] = useState([])

  useEffect(() => {
    // Update progress and agents from WebSocket/API
  }, [])

  return (
    <main className="min-h-screen px-6 py-8">
      <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Progress Section */}
        <div className="lg:col-span-1">
          <div className="glass-card p-6">
            <h3 className="text-lg font-bold text-white mb-4">Scan Progress</h3>
            <ProgressIndicator 
              current={progress} 
              total={100}
              label="Overall"
              animated={true}
              size="lg"
            />
          </div>
        </div>

        {/* Agent Pipeline */}
        <div className="lg:col-span-2">
          <AgentOrchestrator 
            agents={agents}
            isRunning={progress < 100}
          />
        </div>
      </div>
    </main>
  )
}
```

---

## Tailwind Configuration

The enhanced Tailwind config is already in place with:
- ✅ 10+ smooth animations
- ✅ Custom color palette
- ✅ Glassmorphism utilities
- ✅ Premium button styles
- ✅ Responsive spacing

**No additional setup needed!**

---

## Styling Checklist

- [x] `globals.css` - Enhanced with glassmorphism
- [x] `tailwind.config.ts` - Added animations & effects
- [x] Color palette - Cybersecurity themed
- [x] Typography - Inter + JetBrains Mono
- [x] Components - Reusable UI library
- [x] Animations - Smooth 60fps transitions
- [x] Responsive - Mobile-first design

---

## Testing Premium Features

### 1. Test On Different Screens
```bash
# Start dev server
npm run dev

# Open browser
# Desktop: http://localhost:3000
# Mobile simulation: Chrome DevTools (Ctrl+Shift+M)
```

### 2. Test Animations
- Hover over glass cards
- Click buttons and links
- Watch entrance animations

### 3. Test Responsiveness
- Resize browser window
- Test on actual mobile devices
- Check safe area insets (notch handling)

---

## Performance Verification

### Lighthouse Audit
```bash
# In VS Code
# 1. Open DevTools (F12)
# 2. Go to Lighthouse tab
# 3. Run audit
# Target: 90+ Performance, 95+ Accessibility
```

### Animation Performance
- Open DevTools Performance tab
- Record interaction
- Should see 60fps (green bars)
- No jank or stuttering

---

## Color Reference

Use these utilities in your components:

```tsx
// Text colors
className="text-cyan-400"      // Primary cyan
className="text-purple-400"    // Secondary purple  
className="text-green-400"     // Success green
className="text-red-400"       // Error red
className="text-yellow-400"    // Warning yellow

// Background colors (with opacity)
className="bg-cyan-500/10"     // Subtle cyan
className="bg-purple-500/20"   // Visible purple
className="bg-red-500/10"      // Subtle red

// Borders
className="border-cyan-500/30"    // Cyan border
className="border-white/10"       // Subtle border
className="border-white/20"       // Visible border
```

---

## CSS Classes Reference

### Cards & Containers
- `.glass-card` - Glassmorphic card with glow
- `.glass-card p-6` - Padded glass card
- `.separator-glow` - Glowing separator line

### Inputs & Forms
- `.input-glass` - Glassmorphic input field
- `.input-glass w-full` - Full-width input

### Buttons
- `.btn-primary` - Gradient primary button
- `.btn-secondary` - Muted secondary button
- `.btn-glass` - Glassmorphic button

### Text
- `.gradient-text` - Animated gradient text
- `.badge-gradient` - Gradient badge

### Effects
- `.glow-cyan` - Cyan drop shadow glow
- `.glow-purple` - Purple drop shadow glow
- `.glow-green` - Green drop shadow glow

### Status Badges
- `.pill-critical` - Red critical badge
- `.pill-high` - Orange high badge
- `.pill-medium` - Yellow medium badge
- `.pill-low` - Blue low badge
- `.pill-info` - Cyan info badge

---

## Troubleshooting

### Animation not smooth?
- Check browser performance (Chrome > 90)
- Disable extensions that affect DOM
- Verify GPU acceleration enabled

### Colors look different?
- Clear browser cache (Ctrl+Shift+Delete)
- Check if dark mode is enabled
- Verify `tailwind.config.ts` is updated

### Components not importing?
- Verify import path: `@/components/ui`
- Check file exists: `components/ui/index.ts`
- Restart dev server: `npm run dev`

### Responsive not working?
- Check `tailwindcss` version (should be 3.4.4+)
- Verify breakpoints in config
- Test with DevTools device emulation

---

## Next: Advanced Customization

Once premium pages are live, you can:

1. **Add real API integration** to components
2. **Customize color theme** via CSS variables
3. **Add dark/light mode toggle**
4. **Implement WebSocket** for live updates
5. **Add accessibility features** (keyboard nav, screen readers)
6. **Create more premium pages** using the same patterns

---

## 📞 Support

For detailed documentation, see:
- `DESIGN_SYSTEM.md` - Complete design documentation
- `IMPLEMENTATION_GUIDE.md` - Full implementation guide
- Component files - Inline TypeScript/JSX comments

Happy hacking! 🚀✨
