# SentinelAI Premium UI Documentation

## 🎨 Design System

### Colors & Theme
- **Primary**: Cyan (`#00d4ff`) - Used for active states, primary CTAs
- **Secondary**: Purple (`#a855f7`) - Used for alternative CTAs, exam features
- **Accent**: Green (`#00ff88`) - Success states
- **Background**: Dark gradient (`#0a0a0f` → `#1a1a2e`)
- **Glass**: White/10 opacity for glassmorphic effects

### Typography
- **Font Family**: Inter (body), JetBrains Mono (code/terminal)
- **Font Weights**: 300-900
- **Letter Spacing**: 0.3px for refined look

## 🎯 Premium Components

### 1. Glass Card (`.glass-card`)
Glassmorphic card with blur effect and subtle glow
```tsx
<div className="glass-card p-6">
  {/* Content */}
</div>
```
Features:
- Backdrop blur (xl)
- Subtle white border with hover effect
- Inner glow effect with drop shadow
- Smooth transitions on hover

### 2. Input Glass (`.input-glass`)
Premium input field with glassmorphic styling
```tsx
<input className="input-glass" type="text" placeholder="..." />
```
Features:
- Transparent background with backdrop blur
- Cyan focus ring
- Smooth transitions

### 3. Button Styles

#### Primary Button (`.btn-primary`)
Gradient filled button for primary actions
```tsx
<button className="btn-primary">Launch Scan</button>
```

#### Secondary Button (`.btn-secondary`)
Glass button for secondary actions
```tsx
<button className="btn-secondary">Cancel</button>
```

#### Glass Button (`.btn-glass`)
Glassmorphic button with shimmer effect
```tsx
<button className="btn-glass">Action</button>
```

## 🎬 Animations

### Available Animations
- `animate-blink` - Terminal cursor blinking
- `animate-glow-pulse` - Glowing pulse effect
- `animate-float` - Floating motion
- `animate-shimmer` - Shimmer sweep
- `animate-scan-line` - Scanning effect
- `animate-pulse-ring` - Expanding ring
- `animate-blob` - Organic blob movement
- `animate-gradient-shift` - Gradient animation
- `animate-slide-up` - Slide up entrance
- `animate-slide-down` - Slide down entrance
- `animate-scale-in` - Scale in entrance
- `animate-bounce-in` - Bounce in entrance

## 🧩 UI Components

### ProgressIndicator
Real-time progress with animated shimmer
```tsx
<ProgressIndicator 
  current={75} 
  total={100} 
  label="Scan Progress"
  showPercentage={true}
  size="md"
/>
```

### AgentOrchestrator
Multi-agent pipeline visualization
```tsx
<AgentOrchestrator 
  agents={agentList}
  isRunning={true}
  title="Agent Orchestra"
/>
```

### ScanResultCard
Premium result card with trend indicators
```tsx
<ScanResultCard
  title="Vulnerabilities Found"
  value="24"
  icon="⚠️"
  color="red"
  trend="up"
  trendValue="12%"
/>
```

### StatsDashboard
Multi-stat dashboard grid
```tsx
<StatsDashboard
  title="Security Metrics"
  stats={stats}
  columns={4}
/>
```

## 🎨 Tailwind Utilities

### Utility Classes
- `.glass-card` - Glassmorphic card
- `.input-glass` - Glassmorphic input
- `.btn-primary` - Primary button
- `.btn-secondary` - Secondary button
- `.btn-glass` - Glass button
- `.badge-gradient` - Gradient badge
- `.gradient-text` - Animated gradient text
- `.glow-cyan` - Cyan glow effect
- `.glow-purple` - Purple glow effect
- `.glow-green` - Green glow effect
- `.separator-glow` - Glowing separator line

### Severity Pills
- `.pill-critical` - Red critical badge
- `.pill-high` - Orange high badge
- `.pill-medium` - Yellow medium badge
- `.pill-low` - Blue low badge
- `.pill-info` - Cyan info badge

## 📱 Responsive Design

All components use `sm:` breakpoints for mobile optimization:
- Mobile-first approach
- Touch-friendly padding (8px min)
- Responsive typography
- Safe area considerations for notched devices

## 🌙 Dark Mode

Built-in dark mode with:
- Readable contrast ratios (WCAG AA+)
- Reduced motion support
- Accessible color combinations

## 🚀 Performance Optimizations

- Backdrop blur with fallbacks
- Efficient animations (transform/opacity)
- GPU acceleration for smooth 60fps
- Lazy loading of heavy components
- Optimized shadows (not on large elements)

## 📖 Usage Examples

### Premium Dashboard Page
```tsx
import { ProgressIndicator, AgentOrchestrator, StatsDashboard } from "@/components/ui"

export default function Dashboard() {
  return (
    <main className="min-h-screen px-6 py-8 relative overflow-hidden">
      {/* Background blobs */}
      <div className="absolute inset-0 pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-cyan-500/10 rounded-full blur-3xl animate-blob" />
      </div>

      <div className="relative z-10">
        <h1 className="text-4xl font-bold gradient-text mb-8">Security Dashboard</h1>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="glass-card p-6">
            <ProgressIndicator current={75} total={100} label="Overall Progress" />
          </div>
          
          <div className="glass-card p-6">
            <StatsDashboard stats={stats} />
          </div>
          
          <div className="md:col-span-2">
            <AgentOrchestrator agents={agents} isRunning={true} />
          </div>
        </div>
      </div>
    </main>
  )
}
```

## 🎯 Design Principles

1. **Clarity** - Information hierarchy is clear and scannable
2. **Performance** - Smooth 60fps animations
3. **Accessibility** - WCAG AA+ compliant
4. **Consistency** - Unified design language
5. **Feedback** - Visual feedback for all interactions
6. **Polish** - Attention to detail in transitions
