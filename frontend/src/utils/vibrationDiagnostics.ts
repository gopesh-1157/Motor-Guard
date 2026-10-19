import type { FFTSpectrumData, ISO10816Zone, RULPrognostics, SpectralPeak, MotorState } from '../types'

/**
 * Computes frequency spectrum, bearing defect frequencies, and ISO 10816-3
 * vibration velocity parameters from motor state.
 */
export function computeVibrationDiagnostics(motor: MotorState): FFTSpectrumData {
  const currentVibG = motor.latest.sensors.vibration_g_rms ?? 0.05
  const currentTempC = motor.latest.sensors.temperature_c ?? 35.0
  const healthStatus = motor.latest.inference.health_status ?? 'healthy'

  // Motor shaft speed: 3000 RPM nominal default for RS-775 / industrial test bench
  // Under heavier load or critical faults, RPM drops slightly
  const ratedRpm = motor.electrical_specs?.rated_speed_rpm || 3000
  const slipFactor = healthStatus === 'critical' ? 0.91 : healthStatus === 'warning' ? 0.96 : 0.99
  const rpm = Math.round(ratedRpm * slipFactor)
  const runningFreqHz = Number((rpm / 60).toFixed(2)) // e.g. 50.0 Hz for 3000 RPM

  // Bearing defect multipliers (standard deep groove ball bearing 608/6204 series)
  const bpfoHz = Number((runningFreqHz * 3.05).toFixed(2)) // Outer Race
  const bpfiHz = Number((runningFreqHz * 4.95).toFixed(2)) // Inner Race
  const bsfHz = Number((runningFreqHz * 1.98).toFixed(2))  // Ball Spin
  const ftfHz = Number((runningFreqHz * 0.38).toFixed(2))  // Cage/Train

  // Frequency range: 0 to 400 Hz (at 800 Hz ODR, Nyquist is 400 Hz)
  const stepHz = 1.0
  const maxHz = 400
  const frequencies: number[] = []
  const amplitudes_g: number[] = []
  const amplitudes_mms: number[] = []

  // Background noise floor
  const baseNoiseG = Math.max(0.003, currentVibG * 0.08)

  // Peak tracking
  const peaks: SpectralPeak[] = []

  for (let f = 1; f <= maxHz; f += stepHz) {
    frequencies.push(f)

    // Baseline stochastic noise floor with pink 1/f noise curve
    let ampG = baseNoiseG * (1 + 0.35 * Math.sin(f * 1.7) + 0.2 * Math.cos(f * 3.1)) / Math.sqrt(f * 0.08 + 1)

    // 1x Running Speed Fundamental Peak (Unbalance)
    const d1x = Math.abs(f - runningFreqHz)
    if (d1x < 2.5) {
      const peakAmp = currentVibG * 0.55 * Math.exp(-Math.pow(d1x / 1.0, 2))
      ampG += peakAmp
    }

    // 2x Harmonic Peak (Misalignment / Angular Shaft Deflection)
    const d2x = Math.abs(f - runningFreqHz * 2)
    if (d2x < 2.5) {
      const mult = healthStatus === 'critical' ? 0.45 : healthStatus === 'warning' ? 0.35 : 0.12
      const peakAmp = currentVibG * mult * Math.exp(-Math.pow(d2x / 1.0, 2))
      ampG += peakAmp
    }

    // 3x Harmonic Peak (Looseness / Casing Resonance)
    const d3x = Math.abs(f - runningFreqHz * 3)
    if (d3x < 2.5) {
      const mult = healthStatus === 'critical' ? 0.28 : healthStatus === 'warning' ? 0.18 : 0.05
      const peakAmp = currentVibG * mult * Math.exp(-Math.pow(d3x / 1.0, 2))
      ampG += peakAmp
    }

    // Bearing Outer Race Defect (BPFO) Peak & Sidebands
    const dBPFO = Math.abs(f - bpfoHz)
    if (dBPFO < 2.5) {
      const mult = healthStatus === 'critical' ? 0.65 : healthStatus === 'warning' ? 0.30 : 0.04
      const peakAmp = currentVibG * mult * Math.exp(-Math.pow(dBPFO / 1.2, 2))
      ampG += peakAmp
    }

    // Bearing Inner Race Defect (BPFI) Peak
    const dBPFI = Math.abs(f - bpfiHz)
    if (dBPFI < 2.5) {
      const mult = healthStatus === 'critical' ? 0.50 : healthStatus === 'warning' ? 0.22 : 0.03
      const peakAmp = currentVibG * mult * Math.exp(-Math.pow(dBPFI / 1.2, 2))
      ampG += peakAmp
    }

    // Convert Acceleration (g) to Vibration Velocity (mm/s RMS):
    // v = (a * 9806.65) / (2 * pi * f) in mm/s
    const ampMms = f > 2 ? (ampG * 9806.65) / (2 * Math.PI * f) : 0
    amplitudes_g.push(Number(ampG.toFixed(4)))
    amplitudes_mms.push(Number(ampMms.toFixed(3)))
  }

  // Aggregate ISO 10816-3 Velocity across the 10 Hz - 400 Hz ISO band:
  // Integrated RMS velocity: sqrt(sum(v_i^2))
  let sumSqVelocity = 0
  let countBand = 0
  for (let i = 0; i < frequencies.length; i++) {
    if (frequencies[i] >= 10 && frequencies[i] <= 400) {
      sumSqVelocity += Math.pow(amplitudes_mms[i], 2)
      countBand++
    }
  }
  const isoVelocityMms = countBand > 0 ? Math.sqrt(sumSqVelocity) * 0.707 : 0.5

  // Map to ISO 10816-3 Class I (Electric Motors up to 15 kW):
  // Zone A: < 1.4 mm/s RMS (Good)
  // Zone B: 1.4 - 2.8 mm/s RMS (Acceptable)
  // Zone C: 2.8 - 4.5 mm/s RMS (Alert / Limited Operation)
  // Zone D: > 4.5 mm/s RMS (Danger / Immediate Damage)
  let isoZone: ISO10816Zone = 'Zone A (Good)'
  let isoStatus: 'healthy' | 'warning' | 'critical' = 'healthy'

  if (isoVelocityMms >= 4.5 || currentVibG >= 0.70) {
    isoZone = 'Zone D (Critical)'
    isoStatus = 'critical'
  } else if (isoVelocityMms >= 2.8 || currentVibG >= 0.25 || currentTempC >= 55) {
    isoZone = 'Zone C (Alert)'
    isoStatus = 'warning'
  } else if (isoVelocityMms >= 1.4 || currentVibG >= 0.12) {
    isoZone = 'Zone B (Acceptable)'
    isoStatus = 'healthy'
  }

  // Build Diagnostic Peaks
  peaks.push({
    frequency_hz: runningFreqHz,
    amplitude_g: Number((currentVibG * 0.55).toFixed(3)),
    amplitude_mms: Number(((currentVibG * 0.55 * 9806.65) / (2 * Math.PI * runningFreqHz)).toFixed(2)),
    label: `1x Run Speed (${runningFreqHz} Hz)`,
    fault_type: '1x_RPM',
    severity: currentVibG > 0.4 ? 'warning' : 'nominal',
  })

  peaks.push({
    frequency_hz: Number((runningFreqHz * 2).toFixed(1)),
    amplitude_g: Number((currentVibG * 0.35).toFixed(3)),
    amplitude_mms: Number(((currentVibG * 0.35 * 9806.65) / (2 * Math.PI * (runningFreqHz * 2))).toFixed(2)),
    label: `2x Harmonic (${(runningFreqHz * 2).toFixed(1)} Hz)`,
    fault_type: '2x_Harmonic',
    severity: healthStatus === 'critical' ? 'critical' : healthStatus === 'warning' ? 'warning' : 'nominal',
  })

  if (healthStatus === 'critical' || healthStatus === 'warning' || currentVibG > 0.15) {
    peaks.push({
      frequency_hz: bpfoHz,
      amplitude_g: Number((currentVibG * (healthStatus === 'critical' ? 0.65 : 0.30)).toFixed(3)),
      amplitude_mms: Number(((currentVibG * 0.65 * 9806.65) / (2 * Math.PI * bpfoHz)).toFixed(2)),
      label: `BPFO Outer Race (${bpfoHz} Hz)`,
      fault_type: 'BPFO',
      severity: healthStatus === 'critical' ? 'critical' : 'warning',
    })

    peaks.push({
      frequency_hz: bpfiHz,
      amplitude_g: Number((currentVibG * (healthStatus === 'critical' ? 0.50 : 0.22)).toFixed(3)),
      amplitude_mms: Number(((currentVibG * 0.50 * 9806.65) / (2 * Math.PI * bpfiHz)).toFixed(2)),
      label: `BPFI Inner Race (${bpfiHz} Hz)`,
      fault_type: 'BPFI',
      severity: healthStatus === 'critical' ? 'critical' : 'warning',
    })
  }

  return {
    frequencies,
    amplitudes_g,
    amplitudes_mms,
    peaks,
    rpm,
    running_frequency_hz: runningFreqHz,
    iso_zone: isoZone,
    iso_velocity_mms_rms: Number(isoVelocityMms.toFixed(2)),
    iso_rating_status: isoStatus,
    bearing_frequencies: {
      bpfo_hz: bpfoHz,
      bpfi_hz: bpfiHz,
      bsf_hz: bsfHz,
      ftf_hz: ftfHz,
    },
  }
}

/**
 * Calculates Remaining Useful Life (RUL) and Prognostic Degradation
 * using Arrhenius thermal law and ISO vibration fatigue coefficients.
 */
export function computeRULPrognostics(motor: MotorState): RULPrognostics {
  const tempC = motor.latest.sensors.temperature_c ?? 38.0
  const vibG = motor.latest.sensors.vibration_g_rms ?? 0.05
  const currentA = motor.latest.sensors.current_a ?? 2.0
  const health = motor.latest.inference.health_status ?? 'healthy'

  // Baseline L10h bearing design life: 20,000 continuous operating hours
  const baselineLifeHours = 20000

  // 1. Arrhenius Thermal Acceleration Factor (Rule of thumb: bearing grease life halves every 10°C above 40°C)
  const deltaTemp = Math.max(0, tempC - 40.0)
  const thermalDegradationFactor = Math.pow(2, deltaTemp / 10.0)

  // 2. Vibration Fatigue Stress Multiplier (cubic relationship to dynamic load)
  // Nominal vibration ~ 0.05g -> multiplier 1.0; 0.8g -> multiplier > 12
  const vibrationFactor = Math.max(1.0, Math.pow(vibG / 0.06, 1.8))

  // 3. Electrical / Current Load Factor
  const ratedAmps = motor.electrical_specs?.rated_current_a || 3.0
  const loadFactor = Math.max(1.0, Math.pow(currentA / ratedAmps, 1.5))

  // Combined wear acceleration rate
  const wearRate = thermalDegradationFactor * 0.35 + vibrationFactor * 0.50 + loadFactor * 0.15

  // Health index (0 - 100)
  let healthIndex = 100
  if (health === 'critical' || vibG > 0.70 || tempC > 65) {
    healthIndex = Math.max(12, Math.round(35 - (vibG - 0.70) * 40))
  } else if (health === 'warning' || vibG > 0.20 || tempC > 50) {
    healthIndex = Math.max(45, Math.round(75 - (vibG - 0.20) * 60))
  } else {
    healthIndex = Math.min(100, Math.max(85, Math.round(98 - (vibG / 0.10) * 10)))
  }

  // Estimated RUL in hours
  let estimatedRulHours: number
  if (healthIndex <= 25) {
    estimatedRulHours = Math.round(Math.max(48, (healthIndex / 25) * 240)) // 2 to 10 days
  } else if (healthIndex <= 60) {
    estimatedRulHours = Math.round(240 + ((healthIndex - 25) / 35) * 1200) // 10 to 60 days
  } else {
    estimatedRulHours = Math.round((baselineLifeHours / wearRate) * (healthIndex / 100))
  }

  const degradationPct = 100 - healthIndex
  const daysToMaintenance = Math.max(2, Math.round(estimatedRulHours / 24))

  // Dominant stress factor diagnosis
  let dominantFactor: RULPrognostics['dominant_stress_factor'] = 'NORMAL_WEAR'
  if (vibrationFactor > thermalDegradationFactor && vibrationFactor > loadFactor && vibG > 0.15) {
    dominantFactor = 'MECHANICAL_VIBRATION'
  } else if (thermalDegradationFactor > vibrationFactor && tempC > 48) {
    dominantFactor = 'THERMAL'
  } else if (currentA > ratedAmps * 1.1) {
    dominantFactor = 'ELECTRICAL_OVERLOAD'
  }

  // Failure risk level
  let riskLevel: RULPrognostics['failure_risk_level'] = 'LOW'
  if (healthIndex < 30) riskLevel = 'CRITICAL'
  else if (healthIndex < 55) riskLevel = 'ELEVATED'
  else if (healthIndex < 75) riskLevel = 'MODERATE'

  // Projected 30-day degradation trajectory
  const projectedTrend = []
  const dailyDrift = (vibG * (wearRate * 0.015))
  for (let day = 0; day <= 30; day += 3) {
    const projectedG = Math.min(1.5, Number((vibG + (day * dailyDrift)).toFixed(3)))
    projectedTrend.push({
      day,
      projected_vibration_g: projectedG,
      threshold: 0.80, // Critical vibration threshold
    })
  }

  return {
    estimated_rul_hours: estimatedRulHours,
    confidence: Number((motor.latest.inference.confidence || 0.92).toFixed(2)),
    degradation_percentage: degradationPct,
    health_index: healthIndex,
    failure_risk_level: riskLevel,
    dominant_stress_factor: dominantFactor,
    projected_days_to_maintenance: daysToMaintenance,
    projected_trend: projectedTrend,
  }
}
