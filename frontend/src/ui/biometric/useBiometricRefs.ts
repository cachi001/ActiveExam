import { useRef, useState } from 'react';
import type { OvalTono } from './CaptureOval';
import type { FramingHint } from './framingGuide';
import type { Fase } from './detectionLoop';
import type { FaceLandmark, VisionEngine } from '../../vision/VisionEngine';
import type { BaselineMetrics, SequentialChallenge, TurnDirection } from '../../vision/liveness';
import type { BaselineFrame } from '../../vision/enrollmentChallengeDetector';

export function useBiometricRefs() {
  const videoRef              = useRef<HTMLVideoElement>(null);
  const containerRef          = useRef<HTMLDivElement>(null);
  const streamRef             = useRef<MediaStream | null>(null);
  const rafHandleRef          = useRef<number | null>(null);
  const engineRef             = useRef<VisionEngine | null>(null);
  const lastLandmarksRef      = useRef<FaceLandmark[]>([]);
  const faseRef               = useRef<Fase>('capturando');
  const desafiosRef           = useRef<SequentialChallenge[]>([]);
  const resueltosRef          = useRef<string[]>([]);
  const procesarCompletadoRef = useRef<(() => void) | null>(null);

  const challengeIndexRef           = useRef(0);
  const completadosRef              = useRef(0);
  const baselineRef                 = useRef<BaselineMetrics | null>(null);
  const baselineAccumulatorRef      = useRef<BaselineFrame[]>([]);
  const baselineFrameCountRef       = useRef(0);
  const nosePositionsRef            = useRef<Array<{ x: number; y: number }>>([]);
  const bestReferenceFrameRef       = useRef<HTMLCanvasElement | null>(null);
  const cooldownActiveRef           = useRef(false);
  const cooldownTimerRef            = useRef<ReturnType<typeof setTimeout> | null>(null);
  const desafiosBarajadosRef        = useRef<SequentialChallenge[]>([]);
  const turnDirectionRef            = useRef<TurnDirection>('izquierda');
  const challengeCountsRef          = useRef<Map<SequentialChallenge, number>>(new Map());
  const challengeNeutralFramesRef   = useRef<Map<SequentialChallenge, number>>(new Map());
  const gestureAccumMsRef           = useRef<Map<SequentialChallenge, number>>(new Map());
  const gestureLostMsRef            = useRef<Map<SequentialChallenge, number>>(new Map());
  const lastFrameTimeRef            = useRef<number | null>(null);
  const wasHoldingRef               = useRef<Map<SequentialChallenge, boolean>>(new Map());
  const lastProgressTickFractionRef = useRef(0);

  const livenessWindowRef = useRef<Array<{
    blinkL: number; blinkR: number;
    noseX: number; noseY: number;
    minZ: number; maxZ: number;
    frameTime: number;
  }>>([]);
  const passiveOkRef         = useRef(false);
  const passiveFalseFramesRef = useRef(0);
  const prevFrameDataRef     = useRef<ImageData | null>(null);
  const virtualCameraRef     = useRef(false);
  const wasBlockedByFramingRef = useRef(false);
  const framingHintRef       = useRef<FramingHint | null>(null);
  const framingStableRef     = useRef<{ hint: FramingHint | null; frames: number }>({ hint: null, frames: 0 });
  const luminanceCanvasRef   = useRef<HTMLCanvasElement | null>(null);

  const [fase, setFase]                           = useState<Fase>('capturando');
  const [desafios, setDesafios]                   = useState<SequentialChallenge[]>([]);
  const [resueltos, setResueltos]                 = useState<string[]>([]);
  const [motorListo, setMotorListo]               = useState(false);
  const [camaraLista, setCamaraLista]             = useState(false);
  const [motorError, setMotorError]               = useState<string | null>(null);
  const [fallbackManual, setFallbackManual]       = useState(false);
  const fallbackManualRef                         = useRef(false);
  const [errorMsg, setErrorMsg]                   = useState<string | null>(null);
  const [cooldownActivo, setCooldownActivo]       = useState(false);
  const [retoRecienResuelto, setRetoRecienResuelto] = useState<SequentialChallenge | null>(null);
  const [framingHint, setFramingHint]             = useState<FramingHint | null>(null);
  const [progreso, setProgreso]                   = useState(0);
  const [tonoOvalo, setTonoOvalo]                 = useState<OvalTono>('idle');
  const [turnDirection, setTurnDirection]         = useState<TurnDirection>('izquierda');
  const [stallTip, setStallTip]                   = useState<string | null>(null);

  return {
    videoRef, containerRef, streamRef, rafHandleRef, engineRef,
    lastLandmarksRef, faseRef, desafiosRef, resueltosRef, procesarCompletadoRef,
    challengeIndexRef, completadosRef, baselineRef, baselineAccumulatorRef,
    baselineFrameCountRef, nosePositionsRef, bestReferenceFrameRef,
    cooldownActiveRef, cooldownTimerRef, desafiosBarajadosRef, turnDirectionRef,
    challengeCountsRef, challengeNeutralFramesRef, gestureAccumMsRef,
    gestureLostMsRef, lastFrameTimeRef, wasHoldingRef, lastProgressTickFractionRef,
    livenessWindowRef, passiveOkRef, passiveFalseFramesRef,
    prevFrameDataRef, virtualCameraRef, wasBlockedByFramingRef,
    framingHintRef, framingStableRef, luminanceCanvasRef, fallbackManualRef,
    fase, setFase, desafios, setDesafios, resueltos, setResueltos,
    motorListo, setMotorListo, camaraLista, setCamaraLista,
    motorError, setMotorError, fallbackManual, setFallbackManual,
    errorMsg, setErrorMsg, cooldownActivo, setCooldownActivo,
    retoRecienResuelto, setRetoRecienResuelto,
    framingHint, setFramingHint, progreso, setProgreso, tonoOvalo, setTonoOvalo,
    turnDirection, setTurnDirection, stallTip, setStallTip,
  };
}
