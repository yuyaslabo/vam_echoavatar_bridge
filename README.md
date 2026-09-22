# EchoAvatar → Virt-A-Mate Bridge

An unofficial bridge for using **EchoAvatar** with **Virt-A-Mate (VaM)**.  
DEMO: https://youtu.be/5KwQFCZ8y_Y?si=Dalfl6DBjnh7cgXg  
Original Project: [RobinWitch/EchoAvatar](https://github.com/RobinWitch/EchoAvatar)

> [!NOTE]
> This is an unofficial community-made bridge tool not affiliated with EchoAvatar or MeshedVR.

---

## Overview
Allows EchoAvatar's real-time audio-driven body motion to stream into Virt-A-Mate. If the official EchoAvatar sample works, simply replace the Unity sample with this bridge:

```text
EchoAvatar → [TCP : 12346] → vam_echoavatar_bridge.py → [UDP : 9998] → EchoAvatarReceiver.cs → Virt-A-Mate
```
This bridge synchronizes body motion only. Facial expressions (Face) are not synchronized or controlled.

---  

### Key Updates in this Version 1.1.0
* **Low Latency Implementation:** 
  The data processing pipeline has been optimized to minimize latency.
* **Audio Passthrough:** 
  Not only does the bridge send motion, but it now captures the audio returned from the EchoAvatar engine and streams it directly into the VaM environment.

```text
[Audio Input] → Streamer → EchoAvatar Engine (Linux)
                                 │
                                 ├── (Motion Data) ──> [UDP 9998] ──> EchoAvatarReceiver.cs (VaM)
                                 └── (Audio Return) ──> [UDP 9999] ──> EchoAvatarAudioReceiver.cs (VaM)
```

---

## Setup Instructions
1. Ensure the official EchoAvatar environment and sample work.
2. Install the Python dependencies:
```bash
pip install -r requirements.txt
```
3. Run the Python bridge: `python vam_echoavatar_bridge.py`
4. Load `EchoAvatarReceiver.cs` onto your target **Person Atom**.`EchoAvatarAudioReceiver.cs` onto **AudioSource Atom**.
5. Start the EchoAvatar engine and wait for connection.
6. Start the official EchoAvatar tool:`python tools/pushwav2server.py`.

---

## Network & Components
* **UDP Port:** `9998` `9999`  (other settings match official config)
* **vam_echoavatar_bridge.py**: Converts and routes motion data.
* **EchoAvatarReceiver.cs**: VaM plugin applying the motion.

---

## Requirements & Links
* Virt-A-Mate, Python 3.x, and a working EchoAvatar environment.
* Original Project: [RobinWitch/EchoAvatar](https://github.com/RobinWitch/EchoAvatar)

---

## Hint: VaM Optimization
For VaM users, some optional adjustments can be made in the official EchoAvatar inference script to optimize performance and movement:

* **Disable Face inference**  
  If you only need body motion, you can comment out the Face-related inference code to avoid unnecessary processing.
* **Reduce horizontal translation**  
  In `get_joint_pos(pred_motion)`, you can reduce the amount of character translation:
  ```python
  trans_x *= 0.7  
  trans_y *= 0.7  
  ```
  This can help keep the character's movement more suitable for VaM.

> [!TIP]
> These are optional adjustments for VaM use and are not required for the bridge itself. These adjustments can be made in the official EchoAvatar `scripts/...py` inference script.

---

## Citation
See the full citation details in the referenced documentation/bibtex for *EchoAvatar: Real-time Generative Avatar Animation from Audio Streams* (SIGGRAPH '26).

---

## Disclaimer & License
Unofficial third-party tool provided under the MIT License (applies to repository code only).
