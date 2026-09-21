using System;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Threading;
using UnityEngine;

public class EchoAvatarAudioReceiver : MVRScript
{
    // ============================================================
    // Settings
    // ============================================================

    public int UDP_PORT = 9999;

    public int SAMPLE_RATE = 24000;
    public int CHANNELS = 1;

    // 20 ms = 480 samples @ 24kHz
    public int BLOCK_SAMPLES = 480;

    // AudioSourceに最初に貯めてから再生開始する量
    // 10 blocks = 200 ms
    public int START_BUFFER_BLOCKS = 10;

    public bool AUTO_PLAY = true;

    // ============================================================
    // UDP
    // ============================================================

    private UdpClient udpClient;
    private Thread receiveThread;
    private volatile bool running = false;

    // ============================================================
    // Audio queue
    // ============================================================

	private bool isPlaying = false;
    private Queue<float[]> audioQueue = new Queue<float[]>();
    private object audioQueueLock = new object();

    private float[] currentBlock = null;
    private int currentBlockPosition = 0;

    private int queuedSamples = 0;

    // ============================================================
    // Unity Audio
    // ============================================================

    private AudioSource audioSource;
    private AudioClip streamingClip;

    private bool audioStarted = false;

    // ============================================================
    // Debug
    // ============================================================

    private int receivedPackets = 0;
    private long receivedSamples = 0;
    private int underrunCount = 0;

    private float debugTimer = 0f;


    // ============================================================
    // Init
    // ============================================================

    public override void Init()
    {
        base.Init();

        // --------------------------------------------------------
        // Find AudioSource inside this Atom
        // --------------------------------------------------------

        audioSource = GetComponent<AudioSource>();

	if (audioSource == null)
	{
		AudioSource[] sources =
			containingAtom.gameObject.GetComponentsInChildren<AudioSource>(true);

		if (sources != null && sources.Length > 0)
		{
			audioSource = sources[0];

			SuperController.LogMessage(
				"[EchoAvatarAudioReceiver] AudioSource found: "
				+ audioSource.name
			);
		}
	}

	if (audioSource == null)
	{
		SuperController.LogError(
			"[EchoAvatarAudioReceiver] AudioSource not found in Atom."
		);

		return;
	}

        SuperController.LogMessage(
            "[EchoAvatarAudioReceiver] AudioSource found: "
            + audioSource.name
        );

        // --------------------------------------------------------
        // Create streaming AudioClip
        // --------------------------------------------------------

        streamingClip = AudioClip.Create(
            "EchoAvatarStreamingAudio",
            SAMPLE_RATE,
            CHANNELS,
            SAMPLE_RATE,
            true,
            OnAudioRead,
            OnAudioSetPosition
        );

        audioSource.clip = streamingClip;
        audioSource.loop = true;
        audioSource.playOnAwake = false;
		SuperController.LogMessage(
			"[EchoAvatarAudio] CLIP CREATED: " +
			(streamingClip != null ? streamingClip.name : "NULL")
		);

		SuperController.LogMessage(
			"[EchoAvatarAudio] CLIP ASSIGNED: " +
			(audioSource.clip != null ? audioSource.clip.name : "NULL")
		);

        // --------------------------------------------------------
        // Start UDP
        // --------------------------------------------------------

        StartUDP();

        SuperController.LogMessage(
            "[EchoAvatarAudioReceiver] Started UDP "
            + UDP_PORT
            + " / "
            + SAMPLE_RATE
            + "Hz"
        );
    }


    // ============================================================
    // UDP Start
    // ============================================================

    private void StartUDP()
    {
        try
        {
            udpClient = new UdpClient(UDP_PORT);

            running = true;

            receiveThread = new Thread(ReceiveLoop);
            receiveThread.IsBackground = true;
            receiveThread.Start();
        }
        catch (Exception e)
        {
            SuperController.LogError(
                "[EchoAvatarAudioReceiver] UDP start error: "
                + e.Message
            );
        }
    }


    // ============================================================
    // UDP Receive Thread
    // ============================================================

    private void ReceiveLoop()
    {
        IPEndPoint remoteEP = new IPEndPoint(
            IPAddress.Any,
            0
        );

        while (running)
        {
            try
            {
                byte[] data = udpClient.Receive(
                    ref remoteEP
                );

                if (data == null || data.Length < 2)
                    continue;

                ProcessPCM(data);
            }
            catch (SocketException)
            {
                if (!running)
                    break;
            }
            catch (Exception e)
            {
                if (running)
                {
                    SuperController.LogError(
                        "[EchoAvatarAudioReceiver] Receive error: "
                        + e.Message
                    );
                }
            }
        }
    }


    // ============================================================
    // PCM Decode
    //
    // UDP payload:
    //
    // int16 PCM
    // little endian
    //
    // Example:
    // 480 samples
    // = 960 bytes
    // ============================================================

    private void ProcessPCM(byte[] data)
    {
        int sampleCount = data.Length / 2;

        if (sampleCount <= 0)
            return;

        float[] samples = new float[sampleCount];

        for (int i = 0; i < sampleCount; i++)
        {
            short pcm =
                (short)(
                    data[i * 2]
                    |
                    (data[i * 2 + 1] << 8)
                );

            samples[i] = pcm / 32768.0f;
        }

        lock (audioQueueLock)
        {
            audioQueue.Enqueue(samples);
            queuedSamples += sampleCount;
        }

        receivedPackets++;
        receivedSamples += sampleCount;
    }


    // ============================================================
    // Unity Audio Thread
    //
    // IMPORTANT:
    // This function is called by Unity's audio thread.
    // Do not perform blocking operations here.
    // ============================================================

    private void OnAudioRead(float[] data)
    {
		/* SuperController.LogMessage(
			"[EchoAvatarAudio] OnAudioRead: " +
			data.Length +
			" samples"
		); */
        int outputPosition = 0;

        while (outputPosition < data.Length)
        {
            // ----------------------------------------------------
            // Get next block
            // ----------------------------------------------------

            if (currentBlock == null)
            {
                lock (audioQueueLock)
                {
                    if (audioQueue.Count > 0)
                    {
                        currentBlock = audioQueue.Dequeue();
                        currentBlockPosition = 0;
                    }
                }
            }

            // ----------------------------------------------------
            // No audio available
            // ----------------------------------------------------

            if (currentBlock == null)
            {
                data[outputPosition] = 0.0f;
                outputPosition++;

                underrunCount++;

                continue;
            }

            // ----------------------------------------------------
            // Copy current block
            // ----------------------------------------------------

            int remaining =
                currentBlock.Length
                - currentBlockPosition;

            int required =
                data.Length
                - outputPosition;

            int copyCount =
                Math.Min(remaining, required);

            Array.Copy(
                currentBlock,
                currentBlockPosition,
                data,
                outputPosition,
                copyCount
            );

            currentBlockPosition += copyCount;
            outputPosition += copyCount;

            // ----------------------------------------------------
            // Block finished
            // ----------------------------------------------------

            if (currentBlockPosition >= currentBlock.Length)
            {
                currentBlock = null;
                currentBlockPosition = 0;

                lock (audioQueueLock)
                {
                    queuedSamples -=
                        Math.Min(
                            queuedSamples,
                            BLOCK_SAMPLES
                        );
                }
            }
        }
    }


    // ============================================================
    // Audio position callback
    // ============================================================

    private void OnAudioSetPosition(int newPosition)
    {
        // Nothing required.
    }


    // ============================================================
    // Update
    // ============================================================

    private void Update()
    {
        if (audioSource == null)
            return;

        // --------------------------------------------------------
        // Start playback once enough audio is buffered
        // --------------------------------------------------------

        if (!isPlaying && audioQueue.Count >= 10)
		{
			isPlaying = true;

			/* SuperController.LogMessage(
				"[EchoAvatarAudio] PLAY! Queue=" +
				audioQueue.Count
			);

			SuperController.LogMessage(
				"[EchoAvatarAudio] streamingClip=" +
				(streamingClip != null ? streamingClip.name : "NULL")
			);

			SuperController.LogMessage(
				"[EchoAvatarAudio] AudioSource=" +
				audioSource.name +
				" clip=" +
				(audioSource.clip != null ? audioSource.clip.name : "NULL")
			); */

			// ★ここを追加
			audioSource.clip = streamingClip;

			/* SuperController.LogMessage(
				"[EchoAvatarAudio] Reassign clip: " +
				(audioSource.clip != null ? audioSource.clip.name : "NULL")
			); */

			audioSource.Play();

			/* SuperController.LogMessage(
				"[EchoAvatarAudio] After Play: isPlaying=" +
				audioSource.isPlaying +
				" clip=" +
				(audioSource.clip != null ? audioSource.clip.name : "NULL")
			); */
		}

        // --------------------------------------------------------
        // Debug
        // --------------------------------------------------------

        debugTimer += Time.deltaTime;

        if (debugTimer >= 1.0f)
        {
            debugTimer = 0f;

            int queueCount;

            lock (audioQueueLock)
            {
                queueCount = audioQueue.Count;
            }

            float queueMs =
                queueCount
                * BLOCK_SAMPLES
                * 1000.0f
                / SAMPLE_RATE;

            /* SuperController.LogMessage(
                "[EchoAvatarAudio] "
                + "Queue: "
                + queueCount
                + " blocks / "
                + queueMs.ToString("F0")
                + " ms | "
                + "Packets: "
                + receivedPackets
                + " | "
                + "Underrun: "
                + underrunCount
            ); */
        }
    }


    // ============================================================
    // Stop
    // ============================================================

    public void StopAudio()
    {
        if (audioSource != null)
        {
            audioSource.Stop();
        }

        audioStarted = false;
    }


    // ============================================================
    // Clear buffer
    // ============================================================

    public void ClearAudioBuffer()
    {
        lock (audioQueueLock)
        {
            audioQueue.Clear();
            queuedSamples = 0;
        }

        currentBlock = null;
        currentBlockPosition = 0;

        SuperController.LogMessage(
            "[EchoAvatarAudioReceiver] Audio buffer cleared."
        );
    }


    // ============================================================
    // OnDestroy
    // ============================================================

    private void OnDestroy()
    {
        running = false;

        try
        {
            if (udpClient != null)
            {
                udpClient.Close();
                udpClient = null;
            }
        }
        catch
        {
        }

        try
        {
            if (
                receiveThread != null
                && receiveThread.IsAlive
            )
            {
                receiveThread.Join(200);
            }
        }
        catch
        {
        }

        if (audioSource != null)
        {
            audioSource.Stop();
        }

        SuperController.LogMessage(
            "[EchoAvatarAudioReceiver] Stopped."
        );
    }
}