# Software Quality Assurance & Audit Report: Frontend Application (motor-dashboard)

**Target Application:** `c:\Users\gopes\Downloads\project\motor-dashboard`  
**Auditor:** AGENT 2 — FRONTEND QA AGENT  
**Audit Date:** 2026-10-01  
**Target Technology Stack:** React 19.2.8, Vite 8.3.0, Tailwind CSS 4.3.3, Three.js 0.186.1, Recharts 3.10.1, React Router DOM 7.18.4, Oxlint 1.81.0  
**Mode:** READ-ONLY Codebase Inspection, Static Analysis & Empirical Build Validation  

---

## 1. Executive Summary

An exhaustive quality assurance audit and static analysis inspection was conducted on the **MotorGuard** industrial telemetry dashboard (`motor-dashboard`). The audit evaluated application startup and production build integrity, authentication and session lifecycle, role-based access control (RBAC), navigation and routing, 3D digital twin rendering (Three.js), live sensor telemetry visualization, API integration vs. mock simulation disparity, form validation, responsiveness, and code quality.

### Key Audit Findings Summary
- **Total Test Cases Executed:** 21 Distinct Scenarios
- **Passed:** 7 | **Failed:** 14 (Pass Rate: 33.3%)
- **Critical Severity Vulnerabilities:** 3 (Default Admin Auth Bypass, Broken Logout Persistence across Reloads, Complete REST API Disconnect / Zero Backend Sync)
- **High Severity Defects:** 4 (Plaintext Password Storage in `localStorage`, Missing/Orphaned Sidebar Navigation for Core Modules, WebGL GPU Memory Leak on 3D Motor Unmount, Stale Three.js Beacon Sensor Color State)
- **Medium Severity Defects:** 5 (Blinding Light Theme Clash in SCADA Dark Mode, Non-Functional Report Download Buttons, Missing Maintenance Work Order Creation Form, Hardcoded Critical Hazard Banner Text, Monolithic >1.5MB Vite Bundle without Code Splitting)
- **Low Severity / Hygiene Issues:** 2 (React 19 Impure `Math.random()` Render Violations, 179 Oxlint Linter Warnings / Unused Imports)

---

## 2. Test Execution & Evidence Matrix

| Test Case ID & Name | Steps | Expected Result | Actual Result | Status | Severity |
|---|---|---|---|---|---|
| **TC-BUILD-01: Vite Production Build** | Run `npm run build` in `motor-dashboard/` | Clean build producing minified chunks under recommended limits (<500 kB) | Build succeeds in 833ms, but produces a single monolithic chunk `index-DSuVhHr_.js` of **1,507.92 kB** (398 kB gzip). Vite emits chunk size warning. | **FAIL** | MEDIUM |
| **TC-BUILD-02: Oxlint Static Analysis** | Run `npm run lint` (`oxlint`) | Zero errors, zero or minimal warnings | 0 errors, but **179 warnings** across 26 files (react-hooks exhaustive-deps, set-state-in-effect, impure render calls, unused variables). | **FAIL** | LOW |
| **TC-AUTH-01: Default Initial Auth State Bypass** | Clear `localStorage` and navigate directly to `http://localhost:5173/` | Unauthenticated user must be redirected to `/login` | `AppContext.jsx` initializes `currentUser` to `users[0]` (Admin User). User gains instant Admin access without login. | **FAIL** | CRITICAL |
| **TC-AUTH-02: Logout Persistence Across Reload** | Log in, click "Log Out Workstation", then refresh browser (F5) | Session remains terminated; user stays at `/login` | `localStorage.removeItem('motor_health_user')` leaves key null. On reload, `AppContext` defaults right back to `users[0]`. User is re-logged in as Admin! | **FAIL** | CRITICAL |
| **TC-AUTH-03: Credential Handling & Storage** | Inspect `localStorage` after creating or switching users | Passwords hashed or omitted from client storage; credentials validated via backend | Full user records including plaintext `password: "password123"` stored directly in `localStorage.motor_health_users_list`. | **FAIL** | HIGH |
| **TC-AUTH-04: Authenticated /login Redirection** | Authenticate as valid user and navigate manually to `/login` | User redirected to `/` since session is already active | `/login` displays login form again; no redirect logic checks `currentUser`. | **FAIL** | LOW |
| **TC-AUTH-05: RBAC Role Switching (Demo)** | Click user dropdown in Topbar and select different persona | Context updates `currentUser`, Topbar reflects role, permissions recalculate | `switchUser` properly updates state and localStorage; role badge and permissions update immediately. | **PASS** | INFORMATIONAL |
| **TC-NAV-01: ProtectedRoute Role Enforcement** | Access role-restricted URL directly (e.g. `/users` as `operator`) | Screen renders "Access Restricted" alert and blocks sub-component rendering | `ProtectedRoute.jsx` checks `allowedRoles.includes(currentUser.role)`. Renders ISA shield alert and returns link to `/`. | **PASS** | INFORMATIONAL |
| **TC-NAV-02: Sidebar Role-Based Menu Filtering** | Switch roles between Admin, Manager, Technician, Operator | Sidebar dynamically filters navigation items matching permitted views | `filteredNavItems` correctly filters `navItems` based on `roleNavPermissions` mapping. | **PASS** | INFORMATIONAL |
| **TC-NAV-03: Orphaned Routes Navigation Audit** | Check Sidebar navigation for `/edge-impulse` and `/devices` | Sidebar includes clickable links for Edge Impulse and ESP32 Devices | Both `/edge-impulse` and `/devices` are configured in `App.jsx`, but **completely omitted** from `Sidebar.jsx` `navItems` and `roleNavPermissions`. | **FAIL** | HIGH |
| **TC-NAV-04: Catch-All 404 Route Handling** | Navigate to an invalid route (e.g. `/unknown-path`) | Display dedicated 404 Not Found error page | Route `<Route path="*" element={<Navigate to="/" replace />} />` silently redirects to `/` without notifying user of non-existent route. | **PASS** | LOW |
| **TC-API-01: REST API Disparity & Invocations** | Inspect all `.jsx` files for `fetch()` / `axios` backend API calls | Frontend invokes backend endpoints (`/api/motors`, `/api/alerts`, `/api/users`, etc.) | **Zero REST API calls exist** in the entire frontend. Complete reliance on local mock data and `localStorage`. | **FAIL** | CRITICAL |
| **TC-API-02: WebSocket Streaming & Mock Fallback** | Test `WS_URL` connection and simulate backend offline condition | Connects to `ws://localhost:8000/ws/live`; on drop, falls back to local simulation | Connects to real WS if available; on close/error, starts 3000ms `fallbackInterval` using `generateSensorReading()`. | **PASS** | INFORMATIONAL |
| **TC-API-03: Alert Triage & Synchronization** | Click "Acknowledge" or "Resolve" on an active alert in `/alerts` | State persists to backend DB and persists across browser refreshes | Alert state changes only in-memory in React. Not saved to `localStorage` and never sent via `PATCH /api/alerts/{id}`. Reset on F5. | **FAIL** | HIGH |
| **TC-API-04: User CRUD Backend Synchronization** | Add, edit, or delete a user in `/users` | Changes sent to backend `POST/PUT/DELETE /api/users` | Only modifies `localStorage.motor_health_users_list`. Zero synchronization with MongoDB backend collection. | **FAIL** | HIGH |
| **TC-API-05: Motor Registration Backend Synchronization** | Fill "Register Motor" form in `/motors` and submit | Dispatches `POST /api/motors` to register asset and MQTT topic | Saves solely to `localStorage.motor_health_motors`. No backend call is dispatched. | **FAIL** | HIGH |
| **TC-VIEW-01: Overview Hazard Banner Data Binding** | Trigger critical alert on motor other than MTR-003 | Banner displays dynamic motor ID and message from critical alert | Banner displays dynamic count, but alert text is **hardcoded**: *"Immediate bearing inspection required on MTR-003..."*. | **FAIL** | MEDIUM |
| **TC-VIEW-02: Live Monitoring Charts & Stream** | Navigate to `/live`, inspect live charts and 3D twin | Real-time 24-point charts update seamlessly without memory leak | Recharts lines and area charts render smoothly, 2D callouts track 3D coordinates. | **PASS** | INFORMATIONAL |
| **TC-VIEW-03: IndustrialMotor3D Resource Cleanup** | Mount and unmount 3D view repeatedly (switch between Overview and Motors) | WebGL geometries, materials, and textures disposed on unmount | Component only calls `renderer.dispose()`. Meshes, materials, and geometries in scene are never traversed or disposed, leaking GPU memory. | **FAIL** | HIGH |
| **TC-VIEW-04: IndustrialMotor3D Reactive Beacon Color** | Change live sensor values past warning/critical thresholds | 3D sensor beacon meshes change color dynamically (e.g. blue -> red) | 3D beacon material color is instantiated inside mount `useEffect(..., [])`. Changes to `current`, `temp`, or `vibration` do NOT update 3D beacon mesh colors. | **FAIL** | HIGH |
| **TC-VIEW-05: SensorData Synthetic Logs & CSV Export** | Navigate to `/sensor-data` and click "Export CSV" | Logs reflect real historical readings; CSV file downloaded | Logs are 100% synthetically generated via `Array.from({ length: 40 })` in `useMemo`. CSV export works client-side. | **PASS** | MEDIUM |
| **TC-VIEW-06: Maintenance Records CRUD & Modal** | Navigate to `/maintenance`, search for action to add work order | Interface provides "Create Work Order" button and submission form | Page is purely static read-only table. `Plus` icon is imported but unused. No create/edit capability exists. | **FAIL** | MEDIUM |
| **TC-VIEW-07: Reports Generation & Download Actions** | Click "PDF EXPORT" or "DOWNLOAD" on compiled audit reports | Triggers actual document generation or file download | "PDF EXPORT" only sets a temporary 1.2s timeout. Table "DOWNLOAD" buttons have **no `onClick` handler**. Completely inoperative. | **FAIL** | MEDIUM |
| **TC-VIEW-08: Design System & Theme Consistency** | Navigate between Overview, ESP32 Devices, Edge Impulse, Settings | Uniform dark industrial theme (`#0a0e17`, `#111726`, slate-100) | `ESP32Devices.jsx`, `EdgeImpulse.jsx`, and `Settings.jsx` use hardcoded `bg-white`, `border-slate-200`, `text-slate-900`, creating a blinding white contrast. | **FAIL** | MEDIUM |
| **TC-VIEW-09: Mobile Responsive Navigation** | View layout on mobile viewport width (<640px) | Sidebar collapses into off-canvas drawer with toggle button | Sidebar has fixed width (68px or 250px) and `Layout.jsx` forces `marginLeft: sidebarWidth`. No responsive mobile drawer exists. | **FAIL** | LOW |

---

## 3. In-Depth Technical Defect Analysis

### 3.1. [CRITICAL] Authentication Bypass via Default User Initialization
- **File & Lines:** [`src/context/AppContext.jsx` lines 26–33](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/context/AppContext.jsx#L26-L33)
- **Defect Description:**  
  When an anonymous user visits the dashboard for the first time with an empty browser cache, `localStorage.getItem('motor_health_user')` returns `null`. Instead of initializing `currentUser` to `null` and allowing `ProtectedRoute` to redirect the user to `/login`, `AppContext` defaults directly to `users[0]`:
  ```javascript
  const [currentUser, setCurrentUser] = useState(() => {
    try {
      const saved = localStorage.getItem('motor_health_user');
      return saved ? JSON.parse(saved) : users[0]; // <--- CRITICAL SECURITY BYPASS
    } catch {
      return users[0];
    }
  });
  ```
- **Consequence:**  
  Any unauthenticated user navigating to the root URL or any protected page is automatically authenticated as the root **Administrator (`admin@motorhealth.io`)** with unrestricted read/write permissions.

---

### 3.2. [CRITICAL] Broken Logout Session Persistence Across Page Reloads
- **File & Lines:** [`src/context/AppContext.jsx` lines 129–132](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/context/AppContext.jsx#L129-L132)
- **Defect Description:**  
  The `logout()` function removes the `motor_health_user` key from `localStorage` and sets React state `currentUser` to `null`:
  ```javascript
  const logout = () => {
    setCurrentUser(null);
    localStorage.removeItem('motor_health_user');
  };
  ```
  While this temporarily redirects the user to `/login` via React Router, the moment the user hits **Refresh (F5)** or opens the dashboard in a new tab, `localStorage.getItem('motor_health_user')` evaluates to `null`. As detailed in Defect 3.1, `AppContext` defaults right back to `users[0]`.
- **Consequence:**  
  Logging out is an illusion. Any operator logging out at an industrial terminal leaves the workstation fully vulnerable to the next operator simply refreshing the browser to re-gain full administrator privileges.

---

### 3.3. [CRITICAL] Total Absence of Backend REST API Integration
- **File & Lines:** Across all page components (`Motors.jsx`, `Alerts.jsx`, `Users.jsx`, `SensorData.jsx`, `Maintenance.jsx`, `Settings.jsx`, `Reports.jsx`)
- **Defect Description:**  
  A codebase-wide regex search for `fetch(`, `axios`, and HTTP request wrappers revealed **0 occurrences** across all views.
  - The `.env` defines `VITE_API_URL=http://localhost:8000`, but this variable is used solely in `AppContext.jsx` to build the WebSocket stream URL (`ws://localhost:8000/ws/live`).
  - `Settings.jsx` renders an API documentation table listing endpoints like `GET /api/motors`, `PATCH /api/alerts/{id}/acknowledge`, and `POST /api/maintenance`, yet not a single one of these endpoints is ever fetched by the client code!
  - `Alerts.jsx` acknowledgment and resolution functions modify only in-memory React state. A browser reload immediately discards all triage actions.
  - `Users.jsx` user additions/deletions only touch `localStorage`, never synchronizing with MongoDB `users` collection.
  - `SensorData.jsx` generates logs via client-side mathematical random sine waves rather than querying time-series data.
- **Consequence:**  
  The application is effectively a standalone mock prototype disconnected from the FastAPI backend and MongoDB database.

---

### 3.4. [HIGH] Plaintext Password Storage in LocalStorage
- **File & Lines:** [`src/context/AppContext.jsx` lines 16–23, 140–154](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/context/AppContext.jsx#L16-L23) and [`src/pages/Users.jsx` lines 38, 81](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/pages/Users.jsx#L38)
- **Defect Description:**  
  User accounts created in the system are serialized directly into browser `localStorage`:
  ```javascript
  localStorage.setItem('motor_health_users_list', JSON.stringify(updated));
  ```
  Each user object contains the plaintext password: `password: formData.password || 'password123'`.
- **Consequence:**  
  Any client-side script, browser extension, or XSS vector can read all operator and administrator passwords in plain text directly from `window.localStorage`.

---

### 3.5. [HIGH] Orphaned Navigation: Edge Impulse & ESP32 Devices Missing from Sidebar
- **File & Lines:** [`src/components/layout/Sidebar.jsx` lines 22–52](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/components/layout/Sidebar.jsx#L22-L52) vs [`src/App.jsx` lines 83–90](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/App.jsx#L83-L90)
- **Defect Description:**  
  In `App.jsx`, two critical industrial views are declared:
  - `<Route path="edge-impulse" element={<EdgeImpulse />} />`
  - `<Route path="devices" element={<ESP32Devices />} />`
  However, in `Sidebar.jsx`, the `navItems` array and the `roleNavPermissions` dictionary list neither `/edge-impulse` nor `/devices`.
- **Consequence:**  
  Users (even Administrators) cannot navigate to the ESP32 Device Fleet or the Edge Impulse TinyML engine via the UI menus. These features can only be discovered if a user manually guesses and types the URL in the browser address bar.

---

### 3.6. [HIGH] Three.js WebGL Resource Leak on Unmount
- **File & Lines:** [`src/components/3d/IndustrialMotor3D.jsx` lines 567–574](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/components/3d/IndustrialMotor3D.jsx#L567-L574)
- **Defect Description:**  
  In `IndustrialMotor3D.jsx`, the unmount cleanup hook only performs:
  ```javascript
  return () => {
    cancelAnimationFrame(animationFrameId);
    window.removeEventListener('resize', handleResize);
    renderer.dispose();
    if (container.contains(renderer.domElement)) {
      container.removeChild(renderer.domElement);
    }
  };
  ```
  Calling `renderer.dispose()` in Three.js does **not** dispose of the geometries, materials, or textures allocated inside the scene graph. Every time the user navigates between Overview, Live Monitoring, and other tabs, all motor meshes (shafts, toroids, cooling fins, stator casings) remain allocated in GPU VRAM.
- **Consequence:**  
  Frequent navigation rapidly escalates WebGL memory consumption, eventually crashing the browser tab with a WebGL context lost error (`CONTEXT_LOST_WEBGL`).

---

### 3.7. [HIGH] Stale Three.js Beacon Sensor Color State
- **File & Lines:** [`src/components/3d/IndustrialMotor3D.jsx` lines 415–420, 575](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/components/3d/IndustrialMotor3D.jsx#L415-L420)
- **Defect Description:**  
  Sensor indicator beacons are created with initial colors based on sensor thresholds:
  ```javascript
  const currBeacon = new THREE.Mesh(
    new THREE.SphereGeometry(0.07, 16, 16),
    new THREE.MeshBasicMaterial({ color: current > 45 ? 0xef4444 : 0x3b82f6 })
  );
  ```
  However, the enclosing `useEffect` has an empty dependency array `[]`. As live current fluctuates over time (e.g. from 38A to 52A), the 3D beacon mesh material color is never updated. Only the 2D SVG overlay text reflects the updated numbers.
- **Consequence:**  
  The 3D digital twin displays normal blue beacons even when sensor values exceed critical alarm thresholds.

---

### 3.8. [MEDIUM] Blinding Light-Theme Clash in SCADA Dashboard
- **File & Lines:**  
  - [`src/pages/ESP32Devices.jsx` lines 71, 75, 120](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/pages/ESP32Devices.jsx#L71)
  - [`src/pages/EdgeImpulse.jsx` lines 146, 168, 242](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/pages/EdgeImpulse.jsx#L146)
  - [`src/pages/Settings.jsx` lines 8, 29, 83](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/pages/Settings.jsx#L83)
- **Defect Description:**  
  The overarching design system of MotorGuard is an industrial dark theme (`bg-[#0a0e17]`, `bg-[#111726]`, `border-slate-800`, text `slate-100`). However, `ESP32Devices.jsx`, `EdgeImpulse.jsx`, and `Settings.jsx` were built with light-mode classes (`bg-white`, `border-slate-200`, `text-slate-900`, `bg-emerald-50`, `bg-violet-50`).
- **Consequence:**  
  Navigating to any of these three pages results in a harsh, bright white screen that breaks visual continuity, impairs low-light control room ergonomics, and renders certain light gray text unreadable against light backgrounds.

---

### 3.9. [MEDIUM] Inoperative Report Download & Generation Buttons
- **File & Lines:** [`src/pages/Reports.jsx` lines 68–74, 166–169](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/pages/Reports.jsx#L68-L74)
- **Defect Description:**  
  In `Reports.jsx`, clicking "PDF EXPORT" or "CSV" executes a dummy timeout:
  ```javascript
  const handleGenerate = (id, format) => {
    setGenerating(id + format);
    setTimeout(() => {
      setGenerating(null);
      setGenerated(prev => [...prev, id + format]);
    }, 1200);
  };
  ```
  No file blob is created, and no download is triggered. Furthermore, the "DOWNLOAD" button in the Recent Reports table has **no event handler attached at all**:
  ```jsx
  <button className="text-blue-400 hover:text-blue-300 font-bold text-xs flex items-center gap-1 cursor-pointer">
    <Download size={12} /> DOWNLOAD
  </button>
  ```
- **Consequence:**  
  Users cannot generate or download any PDF compliance reports or CSV archives from the Reports section.

---

### 3.10. [MEDIUM] Missing Maintenance Work Order Creation Capability
- **File & Lines:** [`src/pages/Maintenance.jsx` lines 5, 68–199](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/pages/Maintenance.jsx#L5)
- **Defect Description:**  
  The page title claims to provide "Plant CMMS Integration & Work Order Management". The `Plus` icon is imported from `lucide-react`, but there is no "New Work Order" button, modal, or form anywhere in the UI.
- **Consequence:**  
  Maintenance technicians and managers can only inspect a static hardcoded array of 6 existing work orders, with no means to schedule new maintenance tasks or log repairs.

---

### 3.11. [MEDIUM] Hardcoded Critical Hazard Banner Text in Overview
- **File & Lines:** [`src/pages/Overview.jsx` lines 94–96](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/pages/Overview.jsx#L94-L96)
- **Defect Description:**  
  The hazard banner at the top of the Overview page displays:
  ```jsx
  <span className="text-slate-300 ml-2">
    Immediate bearing inspection required on MTR-003. Vibration threshold exceeded.
  </span>
  ```
  While `criticalAlerts.length` is dynamic, the message text is hardcoded to refer specifically to MTR-003 and vibration, even when the critical alarm is generated for MTR-001 (Overheating) or MTR-004.
- **Consequence:**  
  Operators are presented with misleading triage instructions that could misdirect emergency maintenance away from the actual failing asset.

---

### 3.12. [LOW] React 19 StrictMode Impure Render Warnings
- **File & Lines:** [`src/pages/Overview.jsx` lines 52–63](file:///c:/Users/gopes/Downloads/project/motor-dashboard/src/pages/Overview.jsx#L52-L63)
- **Defect Description:**  
  `sensorHistory` in `Overview.jsx` invokes `Math.random()` inside a `useMemo` factory function during component render:
  ```javascript
  const noiseT = (Math.sin(i * 0.8) * 0.6) + ((Math.random() - 0.5) * 0.4);
  ```
  Oxlint flags 4 separate `react(purity)` violations. React 19 treats `useMemo` as a pure computation; invoking non-deterministic functions during render produces unexpected re-renders and breaks component memoization.

---

## 4. Static Analysis & Build Audit

### 4.1. Vite Production Build Metrics
- **Command:** `npm run build`
- **Output:**
  ```text
  vite v8.3.0 building client environment for production...
  ✓ 2485 modules transformed.
  dist/index.html                     0.94 kB │ gzip:   0.54 kB
  dist/assets/index-CxYd8acp.css     61.38 kB │ gzip:  10.65 kB
  dist/assets/index-DSuVhHr_.js   1,507.92 kB │ gzip: 398.14 kB
  (!) Some chunks are larger than 500 kB after minification.
  ✓ built in 833ms
  ```
- **Observations:**
  - Build succeeds without compiler syntax errors.
  - The application lacks code splitting. Heavy libraries (Three.js ~600 kB, Recharts ~400 kB, Lucide icons) are all bundled into a single 1.5 MB JavaScript bundle.
  - First Contentful Paint (FCP) and Time to Interactive (TTI) on industrial field tablets will suffer high latency over cellular/Wi-Fi gateways.

### 4.2. Oxlint Static Code Analysis Metrics
- **Command:** `npm run lint` (`oxlint`)
- **Total Diagnostics:** 179 Warnings, 0 Errors across 26 files in 152ms.
- **Diagnostic Distribution by Rule:**
  - `eslint(no-unused-vars)`: **162 warnings** (dead imports and unreferenced variables across almost every page).
  - `react(purity)`: **4 warnings** (`Math.random()` called during render in `Overview.jsx`).
  - `react(set-state-in-effect)`: **4 warnings** (synchronous `setState` inside `useEffect` causing cascading render loops in `LiveMonitoring.jsx`, `EdgeImpulse.jsx`, `IndustrialMotor3D.jsx`).
  - `react-hooks(exhaustive-deps)`: **9 warnings** (stale closure bugs in `IndustrialMotor3D.jsx`, `Overview.jsx`, `LiveMonitoring.jsx`).

---

## 5. Comprehensive Remediation Roadmap

### 5.1. Priority 1 (Immediate Security & Session Fixes)
1. **Fix Default User Bypass (`src/context/AppContext.jsx`):**
   ```javascript
   // Correct: Default to null if no valid authenticated session exists
   const [currentUser, setCurrentUser] = useState(() => {
     try {
       const saved = localStorage.getItem('motor_health_user');
       return saved ? JSON.parse(saved) : null;
     } catch {
       return null;
     }
   });
   ```
2. **Remove Plaintext Passwords from LocalStorage:**
   Do not store passwords in `localStorage`. Store only the user session token/profile without `password` properties.

### 5.2. Priority 2 (Routing & Navigation Integrity)
1. **Register Missing Modules in Sidebar (`src/components/layout/Sidebar.jsx`):**
   Add `/edge-impulse` and `/devices` to `navItems` and `roleNavPermissions`:
   ```javascript
   // In navItems:
   { to: '/edge-impulse', icon: Sparkles, label: 'Edge Impulse' },
   { to: '/devices', icon: Cpu, label: 'ESP32 Devices' },

   // In roleNavPermissions:
   admin: [..., '/edge-impulse', '/devices'],
   technician: [..., '/edge-impulse'],
   ```
2. **Add Authenticated Redirect in `src/pages/Login.jsx`:**
   If `currentUser` is already populated, automatically redirect to `/`.

### 5.3. Priority 3 (Real Backend REST Ingestion)
1. **Create an API Service Client (`src/services/api.js`):**
   Implement centralized `fetch` wrappers against `VITE_API_URL`:
   - `fetchMotors()` -> `GET /api/motors`
   - `fetchMotorHistory(id)` -> `GET /api/motors/{id}/history`
   - `acknowledgeAlertApi(id)` -> `PATCH /api/alerts/{id}/acknowledge`
   - `fetchUsersApi()` -> `GET /api/users`
2. Connect `Alerts.jsx`, `Users.jsx`, and `Motors.jsx` to this API client with graceful fallback to mock data when `connectionStatus === 'offline'`.

### 5.4. Priority 4 (3D Graphics & Theme Harmonization)
1. **Dispose Three.js Scene Meshes (`IndustrialMotor3D.jsx`):**
   ```javascript
   return () => {
     cancelAnimationFrame(animationFrameId);
     window.removeEventListener('resize', handleResize);
     scene.traverse((object) => {
       if (object.geometry) object.geometry.dispose();
       if (object.material) {
         if (Array.isArray(object.material)) {
           object.material.forEach(mat => mat.dispose());
         } else {
           object.material.dispose();
         }
       }
     });
     renderer.dispose();
     if (container.contains(renderer.domElement)) {
       container.removeChild(renderer.domElement);
     }
   };
   ```
2. **Refactor Light Theme Pages to Dark Industrial:**
   Convert `ESP32Devices.jsx`, `EdgeImpulse.jsx`, and `Settings.jsx` from `bg-white` and `border-slate-200` to `bg-[#111726]`, `border-slate-800`, and `text-slate-100`.
3. **Implement Route-Level Code Splitting (`src/App.jsx`):**
   Wrap route page imports with `React.lazy()` (e.g. `const Overview = lazy(() => import('./pages/Overview'))`) and `<Suspense>` to reduce initial bundle size from 1.5MB to <250kB.

---

**Report Certification:**  
*Audited and certified by AGENT 2 — FRONTEND QA AGENT.*
