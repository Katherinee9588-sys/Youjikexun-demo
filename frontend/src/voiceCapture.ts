export interface ActiveVoiceCapture {
  stop: () => Promise<ArrayBuffer>;
  cancel: () => void;
}

function encodeWav(chunks: Float32Array[], sampleRate: number): ArrayBuffer {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  if (length === 0) {
    throw new Error("没有采集到音频，请按住后再说话。");
  }

  const samples = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    samples.set(chunk, offset);
    offset += chunk.length;
  }

  const bytesPerSample = 2;
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
  const view = new DataView(buffer);
  const writeText = (position: number, value: string) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(position + index, value.charCodeAt(index));
    }
  };

  writeText(0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeText(8, "WAVE");
  writeText(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 16, true);
  writeText(36, "data");
  view.setUint32(40, samples.length * bytesPerSample, true);

  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(44 + index * bytesPerSample, sample * 0x7fff, true);
  }
  return buffer;
}

export async function startVoiceCapture(): Promise<ActiveVoiceCapture> {
  if (navigator.mediaDevices?.getUserMedia === undefined) {
    throw new Error("当前浏览器不支持麦克风采集。");
  }

  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const AudioContextConstructor = window.AudioContext;
  if (AudioContextConstructor === undefined) {
    stream.getTracks().forEach((track) => track.stop());
    throw new Error("当前浏览器不支持音频编码。");
  }

  const context = new AudioContextConstructor();
  const source = context.createMediaStreamSource(stream);
  const processor = context.createScriptProcessor(4096, 1, 1);
  const chunks: Float32Array[] = [];
  let active = true;

  processor.onaudioprocess = (event) => {
    if (!active) return;
    chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
  };
  source.connect(processor);
  processor.connect(context.destination);
  await context.resume();

  const release = () => {
    processor.disconnect();
    source.disconnect();
    stream.getTracks().forEach((track) => track.stop());
  };

  return {
    async stop() {
      active = false;
      release();
      await context.close();
      return encodeWav(chunks, context.sampleRate);
    },
    cancel() {
      if (!active) return;
      active = false;
      release();
      void context.close();
    },
  };
}
