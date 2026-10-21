# TourBox and Lightroom

TourBox Console sits between TourBox hardware and Adobe’s apps. This repository does not speak TourBox’s protocol. Its Classic path is `lightroom-plugin.lrplugin`, which connects to the broker on port 8086. See [SDK integration](../SDK_INTEGRATION.md) and the [setup guide](../README.md).

Name the evidence class when using a claim from this page: **public docs**, or **unknown** where TourBox and Adobe have not published the mechanism. Local readings of an installed Console build are kept outside this tracked tree.

## Two Adobe products

**Lightroom** here means the cloud desktop app. **Lightroom Classic** means the catalog app with Adobe’s Lua plug-in SDK. TourBox’s current Lightroom pages treat them as separate integrations. Classic’s Console 5.12.0 notes include a plug-in activation step. The cloud Lightroom notes list Dynamic Panel behavior and do not include that step.

Adobe’s public cloud surface is the Lightroom Catalog REST API. Adobe’s September 2026 UXP roadmap leaves Lightroom outside that host expansion. Classic’s published plug-in language is Lua. Those facts are the same split already recorded in the [automation-paths synthesis](../reports/Lightroom%20automation%20paths%202026.md).

## What TourBox publishes

| Baseline | Published value | Source |
| :--- | :--- | :--- |
| TourBox Console for Windows | 5.12.0, dated 2026-10-09, Windows 10 or later | [TourBox Console for Windows](https://www.tourboxtech.com/en/downloads/windows/) |
| Dynamic Panel V2 | Lightroom 9.0 or later, or Lightroom Classic 14.1 or later | [Dynamic Panel V2](https://www.tourboxtech.com/en/news/tourbox-dynamic-panel-v2.html) |
| Wired connection check | A new COM port under Device Manager → Ports | [TourBox Console for Windows](https://www.tourboxtech.com/en/downloads/windows/) |
| Wireless Elite / Elite Plus | Console **Add Bluetooth Device** pairing; USB-C takes priority over Bluetooth | [Dual Bluetooth channel](https://www.tourboxtech.com/en/news/tourbox-dual-bluetooth-channel-switch.html) |
| Classic integration | A TourBox plug-in that the 5.12.0 notes tell the user to enable | [TourBox Console for Windows](https://www.tourboxtech.com/en/downloads/windows/) |

TourBox markets Dynamic Panel as one-to-one parameter mirroring, workspace recognition, and reconstructed Tone Curve, Crop, and Color Grading controls, under the label “Deep Lightroom API Integration.” That label is TourBox’s. Adobe’s published Lightroom API is the catalog service at `lr.adobe.io` (assets, albums, metadata, renditions, external XMP). It does not document a local per-detent controller for the running desktop app. The [catalog API notes](../research_notes/Lightroom%20automation%20paths%202026/catalog-api.md) describe that service.

Independent protocol work (TuxBox) describes wired TourBox hardware as USB serial / CDC-ACM and wireless Elite captures as a proprietary Bluetooth GATT service. That is evidence about the hardware-to-Console hop. It is not a Lightroom API.

## Left unpublished

These stay unknown from public sources: the cloud Dynamic Panel mechanism, whether Windows Console synthesizes keyboard input or installs a virtual HID device, per-model firmware minima, the USB VID/PID matrix, measured end-to-end latency, and the Console configuration directory. “No delay” on TourBox’s pages is marketing copy, not a latency figure.

A Max/MSP manual documents a Console socket for press, release, and rotary events. That manual scopes the socket to Max/MSP.

## Surfaces outside this server

Live control in this repository stays on its own Classic plug-in and the SDK modules in [SDK integration](../SDK_INTEGRATION.md). The following are published surfaces with a different job:

| Surface | Role |
| :--- | :--- |
| Lightroom Catalog REST API | Cloud catalog, asset, album, rendition, and external XMP operations |
| UXP and CEP | No current Lightroom host in Adobe’s published extensibility notes |
| MIDI, including MIDI2LR | A Classic plug-in bridge for MIDI hardware, separate from this plug-in |
| TourBox Max/MSP socket | Application-specific Console socket |
| Windows virtual HID | Shown in a community macOS port after that port decodes TourBox; not described as the Windows Console driver |
| Keyboard and mouse synthesis | The generic way Console drives ordinary shortcuts in any app |

Cloud UI automation, when it is used, is a property of a particular Console install. Adobe does not publish it as the Lightroom API. This server’s develop, mask, and metadata tools go through the Classic SDK documented in the [Classic SDK notes](../research_notes/Lightroom%20automation%20paths%202026/classic-sdk.md).

Sources: [TourBox Console for Windows](https://www.tourboxtech.com/en/downloads/windows/), [TourBox for Lightroom](https://www.tourboxtech.com/en/photo-editing/tourbox-for-lightroom-classic/), [Dynamic Panel V2](https://www.tourboxtech.com/en/news/tourbox-dynamic-panel-v2.html), [TourBox Bluetooth channels](https://www.tourboxtech.com/en/news/tourbox-dual-bluetooth-channel-switch.html), [TourBox Max/MSP manual](https://www.tourboxtech.com/oam/manual/max/), [Adobe Lightroom API](https://developer.adobe.com/lightroom/lightroom-api-docs/), [Adobe Lightroom Classic SDK](https://developer.adobe.com/lightroom-classic/), [Adobe UXP roadmap, September 2026](https://blog.developer.adobe.com/en/publish/2026/09/investing-in-the-future-of-creative-cloud-extensibility-uxp-comes-to-our-flagship-applications), [TuxBox](https://github.com/AndyCappDev/tuxbox), [MIDI2LR](https://github.com/rsjaffe/MIDI2LR).
