plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

android {
    namespace = "com.svetlyachok.svetlyachok_mobile"
    // Android 14 (API 34) — целевой и компилируемый SDK по плану.
    compileSdk = 35
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
        isCoreLibraryDesugaringEnabled = true
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_17.toString()
    }

    defaultConfig {
        applicationId = "com.svetlyachok.svetlyachok_mobile"
        // Android 7.0 (API 24) — минимальная версия. Покрывает 99% активных устройств
        // и поддерживает современные WorkManager + permissions API.
        minSdk = 24
        targetSdk = 35
        versionCode = flutter.versionCode
        versionName = flutter.versionName

        // Поддержка multiDex на старых API (< 21 не поддерживаются — но defensive).
        multiDexEnabled = true
    }

    buildTypes {
        release {
            // Подписываем debug-ключом, чтобы `flutter run --release` работал из коробки.
            // На production-вехе — заменить на собственный signing config.
            signingConfig = signingConfigs.getByName("debug")
        }
    }
}

dependencies {
    coreLibraryDesugaring("com.android.tools:desugar_jdk_libs:2.0.4")
}

flutter {
    source = "../.."
}
