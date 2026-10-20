# Third-party components and license scope

The MIT license applies to the original source code, documentation, and wholly
synthetic data generator and fixtures for which this repository's contributors
hold rights. It **does not relicense third-party dependencies or datasets**.

- `android/gradle/wrapper/gradle-wrapper.jar` is the unmodified official Gradle
  wrapper distribution, checksum-allowlisted by the release privacy checker.
  Gradle is distributed under Apache License 2.0; see
  https://github.com/gradle/gradle/blob/master/LICENSE .
- Android Gradle Plugin, Android SDK components, and Android toolchain packages
  are fetched during build; each retains its upstream license.
- Python runtime dependencies (NumPy, pandas, SciPy, scikit-learn, PyTorch,
  TensorFlow, CatBoost, matplotlib and others) remain under their own terms.
- The named Wi-Fi benchmark datasets are **not included**; the repository's
  wholly synthetic examples reproduce neither third-party observations nor the
  private HK building radio map.

If a contributor has introduced third-party code into the repository, its
license and provenance must be identified before publication.
