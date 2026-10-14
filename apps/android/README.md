# Chmaba Cloud POS - Native Android App

## Overview
Native Android application for Chmaba Cloud POS system built with Kotlin and Jetpack Compose.

## Tech Stack
- **Language**: Kotlin 1.9+
- **UI Framework**: Jetpack Compose (Material Design 3)
- **Architecture**: MVVM (Model-View-ViewModel)
- **Dependency Injection**: Hilt
- **Networking**: Retrofit + OkHttp
- **Local Storage**: Room Database
- **Hardware Integration**: 
  - Camera (Barcode/QR scanning)
  - NFC (Card readers)
  - Bluetooth (Receipt printers, cash drawers)
  - USB (POS peripherals)

## Project Structure
```
android/
├── app/
│   ├── src/
│   │   ├── main/
│   │   │   ├── java/com/chmaba/pos/
│   │   │   │   ├── ui/
│   │   │   │   │   ├── theme/          # Design system
│   │   │   │   │   ├── components/     # Reusable components
│   │   │   │   │   ├── screens/        # All screens
│   │   │   │   │   │   ├── auth/       # Login, signup
│   │   │   │   │   │   ├── dashboard/  # Main dashboard
│   │   │   │   │   │   ├── pos/        # POS selling screen
│   │   │   │   │   │   ├── products/   # Product management
│   │   │   │   │   │   ├── orders/     # Order history
│   │   │   │   │   │   ├── customers/  # Customer management
│   │   │   │   │   │   ├── inventory/  # Stock management
│   │   │   │   │   │   └── settings/   # Settings
│   │   │   │   ├── data/
│   │   │   │   │   ├── api/            # API services
│   │   │   │   │   ├── models/         # Data models
│   │   │   │   │   ├── repository/     # Data repositories
│   │   │   │   │   └── local/          # Local database
│   │   │   │   ├── domain/
│   │   │   │   │   ├── usecases/       # Business logic
│   │   │   │   │   └── models/         # Domain models
│   │   │   │   ├── hardware/
│   │   │   │   │   ├── scanner/        # Barcode scanner
│   │   │   │   │   ├── printer/        # Receipt printer
│   │   │   │   │   └── payment/        # Card reader integration
│   │   │   │   └── utils/              # Utilities
│   │   │   └── res/
│   │   │       ├── values/
│   │   │       │   ├── colors.xml
│   │   │       │   ├── strings.xml
│   │   │       │   └── themes.xml
│   │   │       └── drawable/
│   │   └── androidTest/
│   │   └── test/
│   ├── build.gradle.kts
│   └── proguard-rules.pro
├── gradle/
├── build.gradle.kts
├── settings.gradle.kts
└── README.md
```

## Design System

### Colors (matching web)
- **Primary**: `#6957F5` (Purple)
- **Secondary**: `#C4F27C` (Lime)
- **Success**: `#4CAF50` (Green)
- **Error**: `#F44336` (Red)
- **Warning**: `#FF9800` (Orange)
- **Background**: `#F7F7FA` (Light gray)
- **Surface**: `#FFFFFF` (White)
- **OnSurface**: `#202128` (Dark text)

### Typography
- **Display**: 32sp, ExtraBold
- **Headline**: 24sp, ExtraBold
- **Title**: 18sp, SemiBold
- **Body**: 14sp, Medium
- **Label**: 12sp, Regular
- **Caption**: 10sp, Light

### Spacing
- **XXS**: 4dp
- **XS**: 8dp
- **SM**: 12dp
- **MD**: 16dp
- **LG**: 24dp
- **XL**: 32dp
- **XXL**: 48dp

## Getting Started

### Prerequisites
- Android Studio Hedgehog (2023.1.1) or later
- JDK 17+
- Android SDK 34
- Minimum SDK 24 (Android 7.0)

### Build & Run
```bash
# Clone the repository
git clone https://github.com/your-org/chmaba.git
cd chmaba/apps/android

# Open in Android Studio
# or build from command line:
./gradlew assembleDebug

# Install on device
./gradlew installDebug
```

## Features

### Core POS Features
- [x] Product search with barcode scanning
- [x] Category filtering
- [x] Cart management
- [x] Multiple payment methods (Cash, KHQR)
- [x] Receipt generation & printing
- [x] Order history
- [x] Customer management
- [x] Inventory tracking
- [x] Multi-currency support
- [x] Offline mode with sync

### Hardware Integration
- [x] Camera barcode/QR scanning
- [x] NFC card reader support
- [x] Bluetooth thermal printer
- [x] Cash drawer pulse
- [x] USB peripheral support

### User Management
- [x] Multi-user authentication
- [x] Role-based permissions
- [x] Shift management
- [x] Team collaboration

## API Integration
Base URL: `https://api.chmaba.com/v1`

See API documentation at: https://docs.chmaba.com

## License
Proprietary - Chmaba Technologies © 2026
