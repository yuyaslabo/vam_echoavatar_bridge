import socket
import struct
import json
import numpy as np
import time
import threading
import base64
import sounddevice as sd
from collections import deque
from scipy.spatial.transform import Rotation as R
from scipy.spatial.transform import Slerp

is_unity_connected = False

def main():
    # --- 1. ネットワーク設定 ---
    SERVER_IP = "0.0.0.0"       # すべてのインターフェースで待ち受け
    SERVER_PORT = 12346        # Unity側で使っていたポートを指定
    # --- 1. 設定（お使いの環境に合わせて指定してください） ---
    TARGET_IP = "127.0.0.1"
    TARGET_PORT = 9998
    
    UNITY_TCP_IP = "127.0.0.1"
    UNITY_TCP_PORT = 12348  #debug official unity project
    unity_tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    AUDIO_UDP_IP = "127.0.0.1"
    AUDIO_UDP_PORT = 9999

    audio_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    global is_unity_connected
    
    print(f"Connecting to Sample Unity TCP Server on {UNITY_TCP_IP}:{UNITY_TCP_PORT}...")
    try:
        unity_tcp_socket.connect((UNITY_TCP_IP, UNITY_TCP_PORT))
        print("Successfully connected to Sample Unity! Proxy mode initialized.")
        is_unity_connected = True
    except Exception as e:
        print(f"Warning: Could not connect to Sample Unity ({e}). Running without proxy mirroring.")
        is_unity_connected = False
    
    # 提示された88本のボーン順序の配列
    bvh_bone_names = [
       "Root_M", "Hip_R", "HipPart1_R", "Knee_R", "KneePart1_R",
       "Ankle_R", "Toes_R", "ToesEnd_R", "Heel_R", "HeelEnd_R",
       "Spine1_M", "Spine1Part1_M", "Chest_M", "Scapula_R", "Shoulder_R",
       "ShoulderPart1_R", "Elbow_R", "ElbowPart1_R", "Wrist_R",
       "MiddleFinger1_R", "MiddleFinger2_R", "MiddleFinger3_R",
       "MiddleFinger4_R", "ThumbFinger1_R", "ThumbFinger2_R",
       "ThumbFinger3_R", "ThumbFinger4_R", "IndexFinger1_R",
       "IndexFinger2_R", "IndexFinger3_R", "IndexFinger4_R", "Cup_R",
       "PinkyFinger1_R", "PinkyFinger2_R", "PinkyFinger3_R",
       "PinkyFinger4_R", "RingFinger1_R", "RingFinger2_R",
       "RingFinger3_R", "RingFinger4_R", "Neck_M", "NeckPart1_M",
       "Head_M", "Head_angleFix", "L_eye_jnt", "L_eScale_jnt", "Eye_L",
       "L_pupil_jnt", "R_eye_jnt", "R_eScale_jnt", "Eye_R", "R_pupil_jnt",
       "Scapula_L", "Shoulder_L", "ShoulderPart1_L", "Elbow_L",
       "ElbowPart1_L", "Wrist_L", "MiddleFinger1_L", "MiddleFinger2_L",
       "MiddleFinger3_L", "MiddleFinger4_L", "ThumbFinger1_L",
       "ThumbFinger2_L", "ThumbFinger3_L", "ThumbFinger4_L",
       "IndexFinger1_L", "IndexFinger2_L", "IndexFinger3_L",
       "IndexFinger4_L", "Cup_L", "PinkyFinger1_L", "PinkyFinger2_L",
       "PinkyFinger3_L", "PinkyFinger4_L", "RingFinger1_L",
       "RingFinger2_L", "RingFinger3_L", "RingFinger4_L", "Hip_L",
       "HipPart1_L", "Knee_L", "KneePart1_L", "Ankle_L", "Toes_L",
       "ToesEnd_L", "Heel_L", "HeelEnd_L"
    ]
    bone_to_idx = {name: i for i, name in enumerate(bvh_bone_names)}
    
    #'Toes_R': { 'parent': 'Ankle_R', 'offset': [-0.0970, 0.1542, 0.0000], 'init_rot': [-0.0019, 0.0055, -0.6214, 0.7835] },
    #'Toes_L': { 'parent': 'Ankle_L', 'offset': [0.0970, -0.1542, 0.0000], 'init_rot': [-0.0019, 0.0055, -0.6214, 0.7835] },
    
    bone_setup = {
    'Root_M': { 'parent': 'Global', 'offset': [0.0000, 0.8164, 0.0230], 'init_rot': [0.5000, -0.5000, -0.5000, 0.5000] },
    'Hip_R': { 'parent': 'Root_M', 'offset': [0.0263, 0.0135, -0.0752], 'init_rot': [-0.0030, 1.0000, -0.0031, -0.0018] },
    'HipPart1_R': { 'parent': 'Hip_R', 'offset': [-0.1774, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Knee_R': { 'parent': 'HipPart1_R', 'offset': [-0.1774, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.1130, 0.9936] },
    'KneePart1_R': { 'parent': 'Knee_R', 'offset': [-0.1568, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Ankle_R': { 'parent': 'KneePart1_R', 'offset': [-0.1568, 0.0000, 0.0000], 'init_rot': [0.0155, -0.0035, -0.1101, 0.9938] },
    'Toes_R': { 'parent': 'Ankle_R', 'offset': [-0.0970, -0.5000, 0.0000], 'init_rot': [-0.0019, 0.0055, -0.6214, 0.7835] },
    'ToesEnd_R': { 'parent': 'Toes_R', 'offset': [-0.0776, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Heel_R': { 'parent': 'Ankle_R', 'offset': [0.0000, 0.0000, 0.0000], 'init_rot': [0.9650, 0.2623, 0.0000, 0.0000] },
    'HeelEnd_R': { 'parent': 'Heel_R', 'offset': [-0.1383, 0.0000, 0.0000], 'init_rot': [0.3378, 0.5900, -0.3643, 0.6364] },
    'Spine1_M': { 'parent': 'Root_M', 'offset': [-0.1300, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Spine1Part1_M': { 'parent': 'Spine1_M', 'offset': [-0.0630, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Chest_M': { 'parent': 'Spine1Part1_M', 'offset': [-0.0630, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Scapula_R': { 'parent': 'Chest_M', 'offset': [-0.1504, -0.0213, -0.0514], 'init_rot': [0.0000, -0.7071, 0.0000, 0.7071] },
    'Shoulder_R': { 'parent': 'Scapula_R', 'offset': [-0.0809, -0.0612, 0.0000], 'init_rot': [-0.0372, -0.3264, -0.0124, 0.9444] },
    'ShoulderPart1_R': { 'parent': 'Shoulder_R', 'offset': [-0.1108, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Elbow_R': { 'parent': 'ShoulderPart1_R', 'offset': [-0.1108, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, -0.0788, 0.9969] },
    'ElbowPart1_R': { 'parent': 'Elbow_R', 'offset': [-0.1102, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Wrist_R': { 'parent': 'ElbowPart1_R', 'offset': [-0.1102, 0.0000, 0.0000], 'init_rot': [0.0364, -0.0238, -0.0710, 0.9965] },
    'MiddleFinger1_R': { 'parent': 'Wrist_R', 'offset': [-0.0984, 0.0000, 0.0000], 'init_rot': [0.0267, -0.1645, 0.0679, 0.9837] },
    'MiddleFinger2_R': { 'parent': 'MiddleFinger1_R', 'offset': [-0.0473, 0.0000, 0.0000], 'init_rot': [-0.0013, -0.0530, -0.0088, 0.9986] },
    'MiddleFinger3_R': { 'parent': 'MiddleFinger2_R', 'offset': [-0.0297, 0.0000, 0.0000], 'init_rot': [-0.0032, -0.0771, 0.0016, 0.9970] },
    'MiddleFinger4_R': { 'parent': 'MiddleFinger3_R', 'offset': [-0.0270, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'ThumbFinger1_R': { 'parent': 'Wrist_R', 'offset': [-0.0224, 0.0283, -0.0102], 'init_rot': [-0.6501, -0.0068, -0.2561, 0.7154] },
    'ThumbFinger2_R': { 'parent': 'ThumbFinger1_R', 'offset': [-0.0631, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'ThumbFinger3_R': { 'parent': 'ThumbFinger2_R', 'offset': [-0.0326, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'ThumbFinger4_R': { 'parent': 'ThumbFinger3_R', 'offset': [-0.0316, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'IndexFinger1_R': { 'parent': 'Wrist_R', 'offset': [-0.1012, 0.0249, -0.0030], 'init_rot': [-0.0027, -0.1806, 0.0089, 0.9835] },
    'IndexFinger2_R': { 'parent': 'IndexFinger1_R', 'offset': [-0.0410, 0.0000, 0.0000], 'init_rot': [0.0011, -0.0427, -0.0203, 0.9989] },
    'IndexFinger3_R': { 'parent': 'IndexFinger2_R', 'offset': [-0.0267, 0.0000, 0.0000], 'init_rot': [-0.0189, -0.0732, -0.0301, 0.9967] },
    'IndexFinger4_R': { 'parent': 'IndexFinger3_R', 'offset': [-0.0252, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Cup_R': { 'parent': 'Wrist_R', 'offset': [-0.0462, -0.0229, -0.0059], 'init_rot': [-0.0110, -0.0077, 0.1271, 0.9918] },
    'PinkyFinger1_R': { 'parent': 'Cup_R', 'offset': [-0.0464, -0.0111, -0.0062], 'init_rot': [0.0834, -0.2007, 0.0500, 0.9748] },
    'PinkyFinger2_R': { 'parent': 'PinkyFinger1_R', 'offset': [-0.0361, 0.0000, 0.0000], 'init_rot': [0.0030, -0.0307, -0.0202, 0.9993] },
    'PinkyFinger3_R': { 'parent': 'PinkyFinger2_R', 'offset': [-0.0201, 0.0000, 0.0000], 'init_rot': [0.0119, -0.1254, -0.0354, 0.9914] },
    'PinkyFinger4_R': { 'parent': 'PinkyFinger3_R', 'offset': [-0.0205, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'RingFinger1_R': { 'parent': 'Cup_R', 'offset': [-0.0475, 0.0101, 0.0031], 'init_rot': [0.0480, -0.2003, -0.0142, 0.9785] },
    'RingFinger2_R': { 'parent': 'RingFinger1_R', 'offset': [-0.0436, 0.0000, 0.0000], 'init_rot': [-0.0033, -0.0418, -0.0025, 0.9991] },
    'RingFinger3_R': { 'parent': 'RingFinger2_R', 'offset': [-0.0258, 0.0000, 0.0000], 'init_rot': [0.0023, -0.0559, -0.0224, 0.9982] },
    'RingFinger4_R': { 'parent': 'RingFinger3_R', 'offset': [-0.0241, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Neck_M': { 'parent': 'Chest_M', 'offset': [-0.2067, -0.0519, 0.0000], 'init_rot': [0.0000, 0.0000, -0.0464, 0.9989] },
    'NeckPart1_M': { 'parent': 'Neck_M', 'offset': [-0.0463, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Head_M': { 'parent': 'NeckPart1_M', 'offset': [-0.0463, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0464, 0.9989] },
    'Head_angleFix': { 'parent': 'Head_M', 'offset': [0.0000, 0.0000, 0.0000], 'init_rot': [-0.5000, 0.5000, 0.5000, 0.5000] },
    'L_eye_jnt': { 'parent': 'Head_angleFix', 'offset': [-0.0632, 0.1057, 0.1197], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'L_eScale_jnt': { 'parent': 'L_eye_jnt', 'offset': [0.0000, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Eye_L': { 'parent': 'L_eScale_jnt', 'offset': [0.0000, 0.0000, 0.0000], 'init_rot': [0.7475, 0.0554, -0.6601, -0.0489] },
    'L_pupil_jnt': { 'parent': 'Eye_L', 'offset': [-0.0439, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'R_eye_jnt': { 'parent': 'Head_angleFix', 'offset': [0.0632, 0.1057, 0.1197], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'R_eScale_jnt': { 'parent': 'R_eye_jnt', 'offset': [0.0000, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Eye_R': { 'parent': 'R_eScale_jnt', 'offset': [0.0000, 0.0000, 0.0000], 'init_rot': [-0.6601, -0.0489, 0.7475, 0.0554] },
    'R_pupil_jnt': { 'parent': 'Eye_R', 'offset': [-0.0439, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Scapula_L': { 'parent': 'Chest_M', 'offset': [-0.1504, -0.0213, 0.0514], 'init_rot': [0.7071, 0.0000, 0.7071, 0.0000] },
    'Shoulder_L': { 'parent': 'Scapula_L', 'offset': [0.0809, 0.0612, 0.0000], 'init_rot': [-0.0372, -0.3264, -0.0124, 0.9444] },
    'ShoulderPart1_L': { 'parent': 'Shoulder_L', 'offset': [0.1108, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Elbow_L': { 'parent': 'ShoulderPart1_L', 'offset': [0.1108, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, -0.0788, 0.9969] },
    'ElbowPart1_L': { 'parent': 'Elbow_L', 'offset': [0.1102, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Wrist_L': { 'parent': 'ElbowPart1_L', 'offset': [0.1102, 0.0000, 0.0000], 'init_rot': [0.0364, -0.0238, -0.0710, 0.9965] },
    'MiddleFinger1_L': { 'parent': 'Wrist_L', 'offset': [0.0984, 0.0000, 0.0000], 'init_rot': [0.0267, -0.1645, 0.0679, 0.9837] },
    'MiddleFinger2_L': { 'parent': 'MiddleFinger1_L', 'offset': [0.0473, 0.0000, 0.0000], 'init_rot': [-0.0013, -0.0530, -0.0088, 0.9986] },
    'MiddleFinger3_L': { 'parent': 'MiddleFinger2_L', 'offset': [0.0297, 0.0000, 0.0000], 'init_rot': [-0.0032, -0.0771, 0.0016, 0.9970] },
    'MiddleFinger4_L': { 'parent': 'MiddleFinger3_L', 'offset': [0.0270, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'ThumbFinger1_L': { 'parent': 'Wrist_L', 'offset': [0.0224, -0.0283, 0.0102], 'init_rot': [-0.6501, -0.0068, -0.2561, 0.7154] },
    'ThumbFinger2_L': { 'parent': 'ThumbFinger1_L', 'offset': [0.0631, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'ThumbFinger3_L': { 'parent': 'ThumbFinger2_L', 'offset': [0.0326, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'ThumbFinger4_L': { 'parent': 'ThumbFinger3_L', 'offset': [0.0316, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'IndexFinger1_L': { 'parent': 'Wrist_L', 'offset': [0.1012, -0.0249, 0.0030], 'init_rot': [-0.0027, -0.1806, 0.0089, 0.9835] },
    'IndexFinger2_L': { 'parent': 'IndexFinger1_L', 'offset': [0.0410, 0.0000, 0.0000], 'init_rot': [0.0011, -0.0427, -0.0203, 0.9989] },
    'IndexFinger3_L': { 'parent': 'IndexFinger2_L', 'offset': [0.0267, 0.0000, 0.0000], 'init_rot': [-0.0189, -0.0732, -0.0301, 0.9967] },
    'IndexFinger4_L': { 'parent': 'IndexFinger3_L', 'offset': [0.0252, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Cup_L': { 'parent': 'Wrist_L', 'offset': [0.0462, 0.0229, 0.0059], 'init_rot': [-0.0110, -0.0077, 0.1271, 0.9918] },
    'PinkyFinger1_L': { 'parent': 'Cup_L', 'offset': [0.0464, 0.0111, 0.0062], 'init_rot': [0.0834, -0.2007, 0.0500, 0.9748] },
    'PinkyFinger2_L': { 'parent': 'PinkyFinger1_L', 'offset': [0.0361, 0.0000, 0.0000], 'init_rot': [0.0030, -0.0307, -0.0202, 0.9993] },
    'PinkyFinger3_L': { 'parent': 'PinkyFinger2_L', 'offset': [0.0201, 0.0000, 0.0000], 'init_rot': [0.0119, -0.1254, -0.0354, 0.9914] },
    'PinkyFinger4_L': { 'parent': 'PinkyFinger3_L', 'offset': [0.0205, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'RingFinger1_L': { 'parent': 'Cup_L', 'offset': [0.0475, -0.0101, -0.0031], 'init_rot': [0.0480, -0.2003, -0.0142, 0.9785] },
    'RingFinger2_L': { 'parent': 'RingFinger1_L', 'offset': [0.0436, 0.0000, 0.0000], 'init_rot': [-0.0033, -0.0418, -0.0025, 0.9991] },
    'RingFinger3_L': { 'parent': 'RingFinger2_L', 'offset': [0.0258, 0.0000, 0.0000], 'init_rot': [0.0023, -0.0559, -0.0224, 0.9982] },
    'RingFinger4_L': { 'parent': 'RingFinger3_L', 'offset': [0.0241, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Hip_L': { 'parent': 'Root_M', 'offset': [0.0263, 0.0135, 0.0752], 'init_rot': [1.0000, 0.0030, 0.0018, -0.0031] },
    'HipPart1_L': { 'parent': 'Hip_L', 'offset': [0.1774, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Knee_L': { 'parent': 'HipPart1_L', 'offset': [0.1774, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.1130, 0.9936] },
    'KneePart1_L': { 'parent': 'Knee_L', 'offset': [0.1568, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Ankle_L': { 'parent': 'KneePart1_L', 'offset': [0.1568, 0.0000, 0.0000], 'init_rot': [0.0155, -0.0035, -0.1101, 0.9938] },
    'Toes_L': { 'parent': 'Ankle_L', 'offset': [0.0970, -0.5000, 0.0000], 'init_rot': [-0.0019, 0.0055, -0.6214, 0.7835] },
    'ToesEnd_L': { 'parent': 'Toes_L', 'offset': [0.0776, 0.0000, 0.0000], 'init_rot': [0.0000, 0.0000, 0.0000, 1.0000] },
    'Heel_L': { 'parent': 'Ankle_L', 'offset': [0.0000, 0.0000, 0.0000], 'init_rot': [-0.2623, 0.9650, 0.0000, 0.0000] },
    'HeelEnd_L': { 'parent': 'Heel_L', 'offset': [-0.1383, 0.0000, 0.0000], 'init_rot': [0.3513, 0.6137, -0.3513, 0.6137] },
}
    
    VAM_BONE_ORDER = [
    "abdomen2Control",
    "chestControl",
    "headControl",
    "rHandControl",
    "lHandControl",
    "rFootControl",
    "lFootControl",
    "rElbowControl",
    "lElbowControl",
    "rKneeControl",
    "lKneeControl",
    "rArmControl",
    "lArmControl",
    "rThighControl",
    "lThighControl",
    "rShoulderControl",
    "lShoulderControl",
    "rToeControl",
    "lToeControl",
]

    VAM_BINARY_STRUCT = struct.Struct("<133f")

    VAM_VALUES = [0.0] * 133
    
   # 2. 親子関係とオフセットの自動構築
    bone_hierarchy = []
    bone_offsets = np.zeros((len(bvh_bone_names), 3))
    bone_init_rotations = {}

    for name in bvh_bone_names:
        if name not in bone_setup:
            continue
        setup = bone_setup[name]
        parent_name = setup['parent']
        
        # 親が存在し、かつボーンリストに含まれている場合は階層(エッジ)に追加
        if parent_name in bone_to_idx:
            bone_hierarchy.append((bone_to_idx[name], bone_to_idx[parent_name]))
            
        # 初期オフセットを登録
        bone_offsets[bone_to_idx[name]] = setup['offset']
        bone_init_rotations[bone_to_idx[name]] = R.from_quat(setup['init_rot'])
    
    # ============================================================
    # Frame Buffer & Threading Conditions
    # ============================================================
    # Chunk単位ではなく、受信したChunkを1フレームずつ展開して保持する。
    # これにより「2チャンク固定」の待ち時間をなくし、フレーム数を
    # 基準に再生速度をリアルタイム制御できる。
    frame_buffer = deque()
    buffered_frame_count = 0
    buffer_condition = threading.Condition()

    # ------------------------------------------------------------
    # フレームバッファによる再生速度制御
    #
    # 60fps入力を想定した値。
    # 12 frames ≒ 200ms を通常時の目標バッファとする。
    #
    # フレームは一切捨てない。
    # バッファが目標を超えた場合だけ、1.00～1.15xの範囲で
    # 再生を少し速くして余分な遅延を自然に消化する。
    # ------------------------------------------------------------
    TARGET_BUFFER_FRAMES = 20
    MAX_PLAYBACK_SPEED = 1.30
    NORMAL_SPEED = 1.0
    SPEED_PER_EXTRA_FRAME = 0.01
    SPEED_RESPONSE = 0.005

    # 入力フレームレート。現在のEchoAvatarは60fps系を想定。
    INPUT_FPS = 60.0
    FRAME_DURATION = 1.0 / INPUT_FPS

    # ------------------------------------------------------------
    # UDP送信フレーム間引き
    # True  : 2フレームに1回だけVAMへ送信
    # False : 全フレーム送信
    # ------------------------------------------------------------
    SEND_EVERY_OTHER_FRAME = True

    playback_speed = NORMAL_SPEED
    
    # ============================================================
    # Audio playback
    # ============================================================

    audio_buffer = deque()
    audio_buffer_lock = threading.Lock()

    AUDIO_SAMPLE_RATE = 24000
    AUDIO_CHANNELS = 1
    AUDIO_SAMPLE_WIDTH = 2       # 16bit
    AUDIO_ENABLED = True

    # OutputStream の1回のcallbackサイズ
    # 24000Hz × 20ms = 480 samples
    AUDIO_BLOCKSIZE = 480

    audio_stream = None

    # 現在再生中のPCM chunk
    audio_current = None
    audio_current_pos = 0

    # Audioの再生開始をMotion側にも知らせる
    timeline_started = threading.Event()

    # デバッグ
    audio_played_samples = 0
    audio_underrun_count = 0
    
    def audio_callback(outdata, frames, time_info, status):

        nonlocal audio_current
        nonlocal audio_current_pos
        nonlocal audio_played_samples
        nonlocal audio_underrun_count

        #if status:

            # 毎回表示するとログが大量になるので、
            # 必要な場合だけ確認
            # print(
                # "[Audio][Callback] status:",
                # status
            # )

        # 出力を無音で初期化
        outdata.fill(0)

        output_pos = 0

        while output_pos < frames:

            # ----------------------------------------------------
            # 現在のchunkが無くなったら次のchunkを取得
            # ----------------------------------------------------

            if (
                audio_current is None
                or audio_current_pos >= len(audio_current)
            ):

                with audio_buffer_lock:

                    if len(audio_buffer) > 0:

                        audio_current = audio_buffer.popleft()
                        audio_current_pos = 0

                    else:

                        audio_current = None

                # Queueが空
                if audio_current is None:

                    audio_underrun_count += 1

                    break

            # ----------------------------------------------------
            # 今回コピーできるサンプル数
            # ----------------------------------------------------

            remaining_audio = (
                len(audio_current)
                - audio_current_pos
            )

            remaining_output = (
                frames
                - output_pos
            )

            copy_count = min(
                remaining_audio,
                remaining_output
            )

            # ----------------------------------------------------
            # PCMをOutputStreamへコピー
            # ----------------------------------------------------

            outdata[
                output_pos:
                output_pos + copy_count,
                0
            ] = audio_current[
                audio_current_pos:
                audio_current_pos + copy_count
            ]

            audio_current_pos += copy_count
            output_pos += copy_count

            audio_played_samples += copy_count

    # def audio_playback_worker():

        # global audio_stream

        # print("[Audio] =======================================")
        # print("[Audio] Continuous Audio Playback")
        # print("[Audio] sample rate :", AUDIO_SAMPLE_RATE)
        # print("[Audio] channels    :", AUDIO_CHANNELS)
        # print("[Audio] blocksize   :", AUDIO_BLOCKSIZE)
        # print("[Audio] =======================================")

        # # --------------------------------------------------------
        # # 最初のaudioが到着するまで待つ
        # # --------------------------------------------------------

        # while True:

            # with audio_buffer_lock:

                # if len(audio_buffer) > 0:
                    # break

            # time.sleep(0.001)

        # print(
            # "[Audio] First audio chunk received"
        # )

        # # --------------------------------------------------------
        # # OutputStream生成
        # # --------------------------------------------------------

        # # try:

            # # audio_stream = sd.OutputStream(
                # # samplerate=AUDIO_SAMPLE_RATE,
                # # channels=AUDIO_CHANNELS,
                # # dtype="int16",
                # # blocksize=AUDIO_BLOCKSIZE,
                # # callback=audio_callback
            # # )

            # # print(
                # # "[Audio] OutputStream created"
            # # )

            # # # ----------------------------------------------------
            # # # Motionと共通のタイムライン開始
            # # # ----------------------------------------------------

            # # print(
                # # "[Audio] Starting shared timeline..."
            # # )

            # # audio_stream.start()

            # # timeline_started.set()

            # # print(
                # # "[Audio] Timeline START"
            # # )

        # # except Exception as e:

            # # print(
                # # "[Audio] OutputStream ERROR:",
                # # repr(e)
            # # )

            # # import traceback
            # # traceback.print_exc()

            # return

        # # --------------------------------------------------------
        # # Stream監視
        # # --------------------------------------------------------

        # while True:

            # time.sleep(1.0)

            # with audio_buffer_lock:
                # queue_count = len(audio_buffer)

            # played_ms = (
                # audio_played_samples
                # / AUDIO_SAMPLE_RATE
                # * 1000.0
            # )

            # # print(
                # # "[Audio]"
                # # " Queue:", queue_count,
                # # "| Played:", int(played_ms), "ms",
                # # "| Underrun:", audio_underrun_count
            # # )

    def decode_audio(audio_data):

        """
        data_dict["audio"] を numpy int16 PCM に変換
        """

        # print("[Audio][Decode] input type:",type(audio_data).__name__)

        # --------------------------------------------------------
        # Base64
        # --------------------------------------------------------
        if isinstance(audio_data, str):

            print(
                "[Audio][Decode] Base64 string length:",
                len(audio_data)
            )

            try:
                import base64

                raw = base64.b64decode(audio_data)

                print(
                    "[Audio][Decode] Base64 decoded bytes:",
                    len(raw)
                )

                audio = np.frombuffer(
                    raw,
                    dtype=np.int16
                ).copy()

            except Exception as e:

                print(
                    "[Audio][Decode] Base64 decode ERROR:",
                    repr(e)
                )

                return None

        # --------------------------------------------------------
        # integer array
        # --------------------------------------------------------
        elif isinstance(audio_data, list):

            #print("[Audio][Decode] list length:",len(audio_data))

            if len(audio_data) == 0:

                #print("[Audio][Decode] WARNING: empty audio list")

                return None

            try:

                audio_array = np.asarray(
                    audio_data
                )

                #print("[Audio][Decode] numpy dtype:",audio_array.dtype)
                #print("[Audio][Decode] numpy shape:",audio_array.shape)
                #print( "[Audio][Decode] min/max:",audio_array.min(),audio_array.max())

                if np.issubdtype(audio_array.dtype, np.floating):

                    # print("[Audio][Decode] detected normalized FLOAT audio")

                    audio = np.clip(
                        audio_array,
                        -1.0,
                        1.0
                    )

                    audio = (
                        audio * 32767.0
                    ).astype(np.int16)

                else:

                    print(
                        "[Audio][Decode] detected INTEGER audio"
                    )

                    audio = audio_array.astype(
                        np.int16
                    )

            except Exception as e:

                print(
                    "[Audio][Decode] array conversion ERROR:",
                    repr(e)
                )

                return None

        else:

            print(
                "[Audio][Decode] UNKNOWN audio type:",
                type(audio_data)
            )

            return None

        # --------------------------------------------------------
        # 結果確認
        # --------------------------------------------------------

        if audio is None or len(audio) == 0:

            print(
                "[Audio][Decode] ERROR: decoded audio is empty"
            )

            return None


        return audio


    

    # ============================================================
    # TCP受信Worker (推論データをノンストップで回収してキューへ投入)
    # ============================================================
    def receive_worker(client_socket):
        global is_unity_connected
        nonlocal buffered_frame_count
        nonlocal playback_speed
        print("\n[Thread] Receive Worker Started.")
        while True:
            # ----------------------------------------------------
            # 1. 4 byte Header
            # ----------------------------------------------------
            header = b""
            while len(header) < 4:
                chunk = client_socket.recv(4 - len(header))
                if not chunk:
                    print("\n[Thread] Client disconnected.")
                    return
                header += chunk

            message_size = struct.unpack(">i", header)[0]

            # ----------------------------------------------------
            # 2. JSON本体
            # ----------------------------------------------------
            message_bytes = b""
            while len(message_bytes) < message_size:
                chunk = client_socket.recv(message_size - len(message_bytes))
                if not chunk:
                    print("\n[Thread] Client disconnected while reading message.")
                    return
                message_bytes += chunk
                
            ## unity debug mode
            # ★【追加】サンプルUnityへのTCPプロキシ（横流し転送）
            if is_unity_connected:
                try:
                    # Unity側のC#スクリプト(ServerLoop)は、「4バイトのヘッダー(Big-Endian)」を
                    # 先に読み込んでメッセージサイズを把握する仕様になっています。
                    # そのため、受信したデータのサイズをBig-Endianの4バイト(>i)にパッキングして、
                    # メッセージ本体の前にUnityへ送り付けます。
                    unity_header = struct.pack(">i", len(message_bytes))
                    
                    # ヘッダーと本体をそのまま横流し送信
                    unity_tcp_socket.sendall(unity_header)
                    unity_tcp_socket.sendall(message_bytes)
                except Exception as e:
                    print(f"Proxy Error: Connection to Unity lost ({e})")
                    is_unity_connected = False

            # ----------------------------------------------------
            # 3. JSON Decode
            # ----------------------------------------------------
            try:
                json_str = message_bytes.decode("utf-8")
                data_dict = json.loads(json_str)
            except Exception as e:
                print(f"\n[Thread] JSON decode error: {e}")
                continue

            # ----------------------------------------------------
            # 4. Data Check
            # ----------------------------------------------------
            if "pose" not in data_dict or "trans" not in data_dict:
                continue

            frame_count = min(len(data_dict["pose"]), len(data_dict["trans"]))
            if frame_count <= 0:
                continue
                
            if AUDIO_ENABLED and "audio" in data_dict:
                
                audio_array = np.asarray(data_dict["audio"])

                # float audio (-1.0 ～ +1.0) → int16 PCM
                if np.issubdtype(audio_array.dtype, np.floating):
                    audio_array = np.clip(audio_array, -1.0, 1.0)
                    audio_int16 = (audio_array * 32767.0).astype(np.int16)
                else:
                    audio_int16 = audio_array.astype(np.int16)
                    
                # 最初のAudioデータを受信した時点でMotion側を開始
                if not timeline_started.is_set():
                    timeline_started.set()
                    print("[Audio] Timeline started")

                # 24kHz / mono
                # 20ms = 480 samples = 960 bytes
                AUDIO_BLOCK_SAMPLES = 480

                for start in range(0, len(audio_int16), AUDIO_BLOCK_SAMPLES):
                    block = audio_int16[start:start + AUDIO_BLOCK_SAMPLES]

                    if len(block) == 0:
                        continue

                    audio_udp_sock.sendto(
                        block.tobytes(),
                        (AUDIO_UDP_IP, AUDIO_UDP_PORT)
                    )

                audio = decode_audio(data_dict["audio"])

                if audio is not None and len(audio) > 0:

                    with audio_buffer_lock:

                        audio_buffer.append(audio)

                        queue_count = len(audio_buffer)

                    # print(
                        # "[Audio][Receive]"
                        # " queued:",
                        # len(audio),
                        # "samples",
                        # "| duration:",
                        # round(
                            # len(audio) / AUDIO_SAMPLE_RATE * 1000
                        # ),
                        # "ms",
                        # "| queue:",
                        # queue_count
                    # )

            # ----------------------------------------------------
            # 5. Chunkを1フレームずつFrame Bufferへ展開
            # ----------------------------------------------------
            # Chunkそのものはキューに積まず、pose/transの対応する
            # 1フレームを個別に保存する。
            with buffer_condition:
                for f_idx in range(frame_count):
                    frame_buffer.append(
                        (
                            data_dict["trans"][f_idx],
                            data_dict["pose"][f_idx]
                        )
                    )

                buffered_frame_count += frame_count
                buffer_count = buffered_frame_count

                # 受信直後のバッファ量を表示。
                # 速度はPlayback Worker側で毎フレーム再計算する。
                current_speed = playback_speed
                buffer_condition.notify()

            


    # ============================================================
    # 再生Worker (キューから計算・パケット化してVAMへ正確なFPSで送信)
    # ============================================================
    def playback_worker():
        nonlocal playback_speed
        nonlocal buffered_frame_count

        # UDPソケットはスレッド開始時に1回だけ生成
        TARGET_IP = "127.0.0.1"
        TARGET_PORT = 9998
        vam_udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 2フレームに1回送信するための連続カウンタ。
        # 60fps入力 × 1/2送信 = 約30fpsでVaMへ送信する。
        send_frame_counter = 0
        print("\n[Thread] Playback Worker Started. Target VAM UDP -> ", TARGET_PORT)
        
        print("[Motion] Waiting for audio timeline...")

        timeline_started.wait()

        print("[Motion] Timeline START")

        while True:
            # ====================================================
            # Frame Bufferから1フレーム取得
            # ====================================================
            with buffer_condition:
                while len(frame_buffer) == 0:
                    buffer_condition.wait()

                current_trans, current_pose = frame_buffer.popleft()
                buffered_frame_count -= 1
                buffer_count = buffered_frame_count

                # ------------------------------------------------
                # フレームバッファ量に応じたリアルタイム速度制御
                #
                # 目標以下なら1.00x。
                # 目標を1フレーム超えるごとに0.01xだけ加速し、
                # 最大1.15xまで。
                #
                # フレームは絶対に捨てない。
                # ------------------------------------------------
                error = buffer_count - TARGET_BUFFER_FRAMES

                if error <= 0:
                    target_speed = 1.0
                else:
                    target_speed = min(
                        1.0 + error * 0.01,
                        MAX_PLAYBACK_SPEED
                    )

                # 実際の速度を一気に変更しない
                if playback_speed < target_speed:
                    playback_speed = min(
                        playback_speed + SPEED_RESPONSE,
                        target_speed
                    )
                else:
                    playback_speed = max(
                        playback_speed - SPEED_RESPONSE,
                        target_speed
                    )

                current_speed = playback_speed

            # ====================================================
            # 1フレームの再生
            # ====================================================

                # --- 1. mainController（シーンの絶対原点）は初期位置 (0,0,0) で完全に固定 ---
                payload_parts = [

                ]

                                # --- 2. VAMの正確な初期値データ（肩・太もも追加の完全版） ---
                # ============================================================
                # VAM Control Point 初期値
                # ============================================================

                raw_bones_data = [
                    # -------------------------
                    # Body
                    # -------------------------
                    ["abdomen2Control",
                     -0.00001, 1.01319, -0.01046,
                      0.00000, 0.00000, 0.00000, 1.00000],

                    ["chestControl",
                      0.00000, 1.14546, -0.03405,
                      0.00121, 0.00000, 0.00000, -1.00000],

                    ["headControl",
                      0.00000, 1.45982, -0.02026,
                      0.00873, 0.00000, 0.00000, 0.99996],

                    # -------------------------
                    # Right Arm
                    # -------------------------
                    ["rShoulderControl",
                      0.01604, 1.30670, 0.00225,
                     -0.07831, 0.11386, 0.26143, 0.95528],

                    ["rArmControl",
                      0.13888, 1.33541, -0.03973,
                     -0.00775, -0.00059, -0.06232, 0.99803],

                    ["rElbowControl",
                      0.43211, 1.30102, -0.03645,
                      0.01232, 0.25312, 0.01448, -0.96725],

                    ["rHandControl",
                      0.64138, 1.31048, 0.07856,
                     -0.06258, -0.23814, -0.00267, 0.96921],

                    # -------------------------
                    # Left Arm
                    # -------------------------
                    ["lShoulderControl",
                     -0.01601, 1.30671, 0.00226,
                     -0.07832, -0.11383, -0.26149, 0.95527],

                    ["lArmControl",
                     -0.13863, 1.33595, -0.03707,
                     -0.00997, -0.00223, 0.06336, 0.99794],

                    ["lElbowControl",
                     -0.43187, 1.30108, -0.03583,
                      0.01262, -0.25185, -0.01464, -0.96757],

                    ["lHandControl",
                     -0.64138, 1.31048, 0.07856,
                     -0.06258, 0.23814, 0.00267, 0.96921],

                    # -------------------------
                    # Right Leg
                    # -------------------------
                    ["rThighControl",
                      0.08516, 0.86602, -0.01869,
                      0.10144, -0.03480, -0.02017, -0.99403],

                    ["rKneeControl",
                      0.09849, 0.47465, 0.07508,
                     -0.10665, -0.05092, -0.01082, -0.99293],

                    ["rFootControl",
                      0.10876, 0.05731, -0.02720,
                      0.16140, 0.12386, 0.00000, 0.97909],

                    ["rToeControl",
                      0.14170, 0.01637, 0.08565,
                     -0.11732, -0.12890, -0.00381, -0.98469],

                    # -------------------------
                    # Left Leg
                    # -------------------------
                    ["lThighControl",
                     -0.08518, 0.86598, -0.01864,
                      0.10155, 0.03463, 0.02000, -0.99403],

                    ["lKneeControl",
                     -0.09834, 0.47463, 0.07523,
                     -0.10677, 0.05089, 0.01096, -0.99292],

                    ["lFootControl",
                     -0.10876, 0.05731, -0.02720,
                      0.16140, -0.12386, 0.00000, 0.97909],

                    ["lToeControl",
                     -0.14203, 0.01638, 0.08614,
                     -0.11490, 0.12750, 0.00474, -0.98515],
                ]


                vam_init = {
                    b[0]: {
                        "pos": np.array(b[1:4], dtype=float),
                        "rot": R.from_quat(b[4:8])
                    }
                    for b in raw_bones_data
                }

                v_pos = {}
                v_rot = {}


                # ============================================================
                # 1. Root_M → abdomen2Control
                # ============================================================

                scale = 0.010
                scale_y =0.011

                abd_x = current_trans[0] * scale * -1
                abd_y = current_trans[1] * scale_y
                abd_z = current_trans[2] * scale

                root_idx = bone_to_idx["Root_M"]

                rx, ry, rz, rw = current_pose[root_idx]

                v_pos["abdomen2Control"] = np.array([
                    abd_x,
                    abd_y,
                    abd_z
                ])

                # BVH → VAM 座標系変換
                root_rot = R.from_quat([
                    rz * -1,
                    rx * -1,
                    ry,
                    rw
                ])

                v_rot["abdomen2Control"] = (
                    vam_init["abdomen2Control"]["rot"] *
                    root_rot
                )


                # ============================================================
                # 2. VAM側の実際のFKトポロジー
                #
                # BVHの中間骨はここではControl Pointを作らず、
                # 対応する関節の回転として吸収する。
                # ============================================================

                target_hierarchy = [

                    # --------------------------------------------------------
                    # Body
                    # --------------------------------------------------------

                    ("chestControl",
                     "abdomen2Control",
                     "Chest_M"),

                    ("headControl",
                     "chestControl",
                     "Head_M"),


                    # --------------------------------------------------------
                    # Right Arm
                    #
                    # Chest
                    #   ↓ Scapula_R
                    #   ↓ Shoulder_R
                    #   ↓ ShoulderPart1_R
                    #   ↓ Elbow_R
                    #   ↓ ElbowPart1_R
                    #   ↓ Wrist_R
                    #
                    # VAM
                    # Chest
                    #   ↓ rShoulder
                    #   ↓ rArm
                    #   ↓ rElbow
                    #   ↓ rHand
                    # --------------------------------------------------------

                    ("rShoulderControl",
                     "chestControl",
                     "Scapula_R"),

                    ("rArmControl",
                     "rShoulderControl",
                     "Shoulder_R"),

                    ("rElbowControl",
                     "rArmControl",
                     "Elbow_R"),

                    ("rHandControl",
                     "rElbowControl",
                     "Wrist_R"),


                    # --------------------------------------------------------
                    # Left Arm
                    # --------------------------------------------------------

                    ("lShoulderControl",
                     "chestControl",
                     "Scapula_L"),

                    ("lArmControl",
                     "lShoulderControl",
                     "Shoulder_L"),

                    ("lElbowControl",
                     "lArmControl",
                     "Elbow_L"),

                    ("lHandControl",
                     "lElbowControl",
                     "Wrist_L"),


                    # --------------------------------------------------------
                    # Right Leg
                    #
                    # Root
                    #   ↓ Hip_R
                    #   ↓ HipPart1_R
                    #   ↓ Knee_R
                    #   ↓ KneePart1_R
                    #   ↓ Ankle_R
                    #   ↓ Toes_R
                    #
                    # VAM
                    # Root
                    #   ↓ rThigh
                    #   ↓ rKnee
                    #   ↓ rFoot
                    #   ↓ rToe
                    # --------------------------------------------------------

                    ("rThighControl",
                     "abdomen2Control",
                     "Hip_R"),

                    ("rKneeControl",
                     "rThighControl",
                     "Knee_R"),

                    ("rFootControl",
                     "rKneeControl",
                     "Ankle_R"),

                    ("rToeControl",
                     "rFootControl",
                     "Toes_R"),


                    # --------------------------------------------------------
                    # Left Leg
                    # --------------------------------------------------------

                    ("lThighControl",
                     "abdomen2Control",
                     "Hip_L"),

                    ("lKneeControl",
                     "lThighControl",
                     "Knee_L"),

                    ("lFootControl",
                     "lKneeControl",
                     "Ankle_L"),

                    ("lToeControl",
                     "lFootControl",
                     "Toes_L"),
                ]


                # ============================================================
                # 3. BVH Quaternion → VAM Quaternion
                #
                # ここは現在まで確認してきた軸変換を使用。
                # ============================================================

                def convert_bvh_rotation(
                    bone_name,
                    jx, jy, jz, jw
                    #R  P  Y
                ):
                    """
                    BVH quaternion [x,y,z,w]
                    →
                    VAM quaternion

                    戻り値は scipy Rotation
                    """
                    if bone_name == "Toes_R":
                        return R.from_quat([
                            jz,
                            -jy,
                            jx,
                            jw
                        ])



                    elif bone_name == "Toes_L":
                        return R.from_quat([
                            jz,
                            jy,
                            -jx,
                            jw
                        ])
                        
                    if bone_name == "Ankle_R":
                        return R.from_quat([
                            jz,
                            jx,
                            jy,
                            jw
                        ])



                    elif bone_name == "Ankle_L":
                        return R.from_quat([
                            jz,
                            -jx,
                            -jy,
                            jw
                        ])
                    # --------------------------------------------------------
                    # Right Knee
                    # --------------------------------------------------------
                    if bone_name == "Knee_R":
                        return R.from_quat([
                            jz,
                            jx,
                            jy,
                            jw
                        ])


                    # --------------------------------------------------------
                    # Left Knee
                    # --------------------------------------------------------
                    elif bone_name == "Knee_L":
                        return R.from_quat([
                            jz,
                            -jx,
                            -jy,
                            jw
                        ])


                    # --------------------------------------------------------
                    # Right Elbow
                    # --------------------------------------------------------
                    elif bone_name == "Elbow_R":
                        return R.from_quat([
                            -jx,
                            jz,
                            jy,
                            jw
                        ])


                    # --------------------------------------------------------
                    # Left Elbow
                    # --------------------------------------------------------
                    elif bone_name == "Elbow_L":
                        return R.from_quat([
                            -jx,
                            -jz,
                            -jy,
                            jw
                        ])


                    # --------------------------------------------------------
                    # Right Shoulder
                    # --------------------------------------------------------
                    elif bone_name == "Shoulder_R":
                        return R.from_quat([
                            -jx,
                            jz,
                            jy,
                            jw
                        ])


                    # --------------------------------------------------------
                    # Left Shoulder
                    # --------------------------------------------------------
                    elif bone_name == "Shoulder_L":
                        return R.from_quat([
                            -jx,
                            -jz,
                            -jy,
                            jw
                        ])


                    # --------------------------------------------------------
                    # Right Hip
                    # --------------------------------------------------------
                    elif bone_name == "Hip_R":
                        return R.from_quat([
                            jz,
                            jx,
                            jy,
                            jw
                        ])


                    # --------------------------------------------------------
                    # Left Hip
                    # --------------------------------------------------------
                    elif bone_name == "Hip_L":
                        return R.from_quat([
                            jz,
                            -jx,
                            -jy,
                            jw
                        ])


                    # --------------------------------------------------------
                    # Wrist
                    # --------------------------------------------------------
                    elif bone_name == "Wrist_R":
                        return R.from_quat([
                            -jx,
                            jz,
                            jy,
                            jw
                        ])


                    elif bone_name == "Wrist_L":
                        return R.from_quat([
                            -jx,
                            -jz,
                            -jy,
                            jw
                        ])


                    # --------------------------------------------------------
                    # その他
                    # --------------------------------------------------------
                    else:
                        return R.from_quat([
                            -jz,
                            -jx,
                            jy,
                            jw
                        ])


                # ============================================================
                # 4. 固定姿勢補正
                #
                # 現在確認済みのVAM/BVH初期姿勢差をここで吸収する。
                # ============================================================
                # R P Y
                def get_fixed_rotation(bone_name):
                    # Ankle
                    if bone_name == "Toes_R":
                        return R.from_euler(
                            "xyz",
                            [-25.0, 0.0, 0.0],
                            degrees=True
                        )

                    if bone_name == "Toes_L":
                        return R.from_euler(
                            "xyz",
                            [-25.0, 0.0, 0.0],
                            degrees=True
                        )
                    
                    

                    # Knee
                    if bone_name == "Knee_R":
                        return R.from_euler(
                            "xyz",
                            [-25.0, 0.0, 0.0],
                            degrees=True
                        )

                    if bone_name == "Knee_L":
                        return R.from_euler(
                            "xyz",
                            [-25.0, 0.0, 0.0],
                            degrees=True
                        )

                    # Hip
                    if bone_name == "Hip_R":
                        return R.from_euler(
                            "xyz",
                            [17.0, 0.0, 0.0],
                            degrees=True
                        )

                    if bone_name == "Hip_L":
                        return R.from_euler(
                            "xyz",
                            [17.0, 0.0, 0.0],
                            degrees=True
                        )

                    # Shoulder
                    if bone_name == "Shoulder_R":
                        return R.from_euler(
                            "xyz",
                            [0.0, 0.0, -70.0],
                            degrees=True
                        )

                    if bone_name == "Shoulder_L":
                        return R.from_euler(
                            "xyz",
                            [0.0, 0.0, 70.0],
                            degrees=True
                        )
                    if bone_name == "Elbow_R":
                        return R.from_euler(
                            "xyz",
                            [0.0, 40.0, 0.0],
                            degrees=True
                        )

                    if bone_name == "Elbow_L":
                        return R.from_euler(
                            "xyz",
                            [0.0, -40.0, 0.0],
                            degrees=True
                        )
                        
                    if bone_name == "Chest_M":
                        return R.from_euler(
                            "xyz",
                            [15.0, 0.0, 0.0],
                            degrees=True
                        )

                    return R.identity()


                # ============================================================
                # 5. 全身FK
                # ============================================================

                for child_id, parent_id, bvh_bone_name in target_hierarchy:

                    # --------------------------------------------------------
                    # Parent
                    # --------------------------------------------------------

                    p_pos = v_pos[parent_id]
                    p_rot = v_rot[parent_id]


                    # --------------------------------------------------------
                    # VAM初期姿勢での親→子オフセット
                    #
                    # これによってVAM上のControl Point間の距離を保持する。
                    # --------------------------------------------------------

                    init_offset = (
                        vam_init[child_id]["pos"]
                        -
                        vam_init[parent_id]["pos"]
                    )


                    # --------------------------------------------------------
                    # BVH joint quaternion
                    # --------------------------------------------------------

                    echo_idx = bone_to_idx[bvh_bone_name]

                    jx, jy, jz, jw = current_pose[echo_idx]


                    # --------------------------------------------------------
                    # BVH → VAM quaternion
                    # --------------------------------------------------------

                    joint_rot = convert_bvh_rotation(
                        bvh_bone_name,
                        jx, jy, jz, jw
                    )


                    # --------------------------------------------------------
                    # 初期姿勢補正
                    # --------------------------------------------------------

                    fixed_rot = get_fixed_rotation(
                        bvh_bone_name
                    )


                    # --------------------------------------------------------
                    # World Rotation
                    #
                    # 親のWorld回転
                    #      ×
                    # VAM Control Point初期回転
                    #      ×
                    # BVH Joint Motion
                    #
                    # --------------------------------------------------------

                    c_rot = (
                        p_rot
                        *
                        vam_init[child_id]["rot"]
                        *
                        fixed_rot
                        *
                        joint_rot
                    )

                    v_rot[child_id] = c_rot


                    # --------------------------------------------------------
                    # World Position
                    #
                    # Control Pointの初期相対位置を
                    # 親のWorld回転で回す。
                    # --------------------------------------------------------

                    v_pos[child_id] = (
                        p_pos
                        +
                        p_rot.apply(init_offset)
                    )


                # ============================================================
                # 6. UDP Packet
                # ============================================================

                i = 0

                for bone_id in VAM_BONE_ORDER:

                    pos = v_pos[bone_id]
                    quat = v_rot[bone_id].as_quat()

                    VAM_VALUES[i] = float(pos[0])
                    VAM_VALUES[i + 1] = float(pos[1]) + 0.14
                    VAM_VALUES[i + 2] = float(pos[2])

                    VAM_VALUES[i + 3] = float(quat[0])
                    VAM_VALUES[i + 4] = float(quat[1])
                    VAM_VALUES[i + 5] = float(quat[2])
                    VAM_VALUES[i + 6] = float(quat[3])

                    i += 7


                payload = VAM_BINARY_STRUCT.pack(*VAM_VALUES)


                # ============================================================
                # 1フレームおきにUDP送信
                # ============================================================

                send_this_frame = (
                    not SEND_EVERY_OTHER_FRAME
                    or (send_frame_counter % 2 == 0)
                )

                send_frame_counter += 1

                if send_this_frame:
                    vam_udp_sock.sendto(
                        payload,
                        (TARGET_IP, TARGET_PORT)
                    )
                    
                # ----------------------------------------------------
                # Debug Output
                # ----------------------------------------------------
                print(
                    f"\r[Frame Buffer]: {buffer_count:3d} frames "
                    f"({buffer_count * FRAME_DURATION * 1000:4.0f} ms) | "
                    f"Speed: {current_speed:.2f}x",
                    end="",
                    flush=True
                )


                # 60fps入力を基準に再生。
                # 1.00x = 約16.67ms/frame
                # 1.15x = 約14.49ms/frame
                time.sleep(FRAME_DURATION / playback_speed)



    # --- 5. TCPサーバー起動 ---
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((SERVER_IP, SERVER_PORT))
    server_socket.listen(1)
    print(f"TCP Server started on port {SERVER_PORT}. Waiting for client connection...")
    
    # audio_thread = threading.Thread(
        # target=audio_playback_worker,
        # daemon=True
    # )

    # audio_thread.start()

    # 再生Workerは1つだけ起動。
    # バッファが空ならCondition.wait()で待機し、データが入れば即再生する。
    playback_thread = threading.Thread(target=playback_worker, daemon=True)
    playback_thread.start()
    print("[Main] Playback thread started. Waiting for data chunks...")

    try:
        while True:
            # 推論エンジン（またはシミュレーター）からの接続を待機
            client_socket, client_address = server_socket.accept()
            print(f"\n[Main] Client connected from {client_address}!")

            # 接続ごとに受信Workerを1つ起動。
            receive_thread = threading.Thread(
                target=receive_worker,
                args=(client_socket,),
                daemon=True
            )
            receive_thread.start()
            print(f"[Main] Receive thread started for {client_address}.")

            # 受信Workerへ処理を渡したら、次の接続を待つ。
            # 既存の接続が切れても再接続可能。

    except KeyboardInterrupt:
        print("\n[Main] Server shutting down by user.")
    finally:
        server_socket.close()
        try:
            client_socket.close()
        except (NameError, OSError):
            pass
        print("[Main] Server socket closed safely.")
            


if __name__ == "__main__":
    main()
