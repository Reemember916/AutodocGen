#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CCS_ROOT="${CCS_ROOT:-/Applications/ti/ccs1220/ccs/tools/compiler/ti-cgt-c2000_22.6.0.LTS}"
CL2000="${CL2000:-$CCS_ROOT/bin/cl2000}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/build_macos}"
DATE_TAG="$(date +%m%d)"
OUT_NAME="${OUT_NAME:-PROJECT-${DATE_TAG}}"

if [[ ! -x "$CL2000" ]]; then
  echo "[ERR] cl2000 not found: $CL2000"
  exit 1
fi

mkdir -p "$OUT_DIR/obj"

COMMON_FLAGS=(
  -v28 -ml -mt --float_support=fpu32
  -Ooff -g
  --diag_warning=225 --display_error_number --diag_wrap=off
)

INCLUDE_FLAGS=(
  --include_path="$ROOT_DIR/Include"
  --include_path="$ROOT_DIR/Include/Common"
  --include_path="$ROOT_DIR/Include/DSPDriver"
  --include_path="$ROOT_DIR/Include/Application"
  --include_path="$ROOT_DIR/Include/Application/DataObtain"
  --include_path="$ROOT_DIR/Include/Application/BIT"
  --include_path="$ROOT_DIR/Include/Application/DataStorage"
  --include_path="$ROOT_DIR/Include/Application/Communication"
  --include_path="$ROOT_DIR/Include/OtherDriver"
  --include_path="$CCS_ROOT/include"
)

# Source order: CodeStartBranch first, then the rest
SOURCES=(
  "Src/Application/DSP2833x_CodeStartBranch.asm"

  "Src/Application/Init.c"
  "Src/Application/Main.c"
  "Src/Application/Synchronous.c"

  "Src/Application/Communication/Comm429RIU.c"
  "Src/Application/Communication/CommCCDL.c"
  "Src/Application/Communication/Comm429KZZZ.c"
  "Src/Application/Communication/Comm422.c"
  "Src/Application/Communication/MaintDataSendPack.c"

  "Src/Application/BIT/MBIT.c"
  "Src/Application/BIT/IFBIT.c"
  "Src/Application/BIT/PuBIT.c"
  "Src/Application/BIT/BITCommon.c"

  "Src/Application/DataObtain/DataObtainIO.c"
  "Src/Application/DataObtain/DataObtainAI.c"

  "Src/Application/Control/Control_Main.c"
  "Src/Application/Control/Control_State.c"
  "Src/Application/Control/Control_Refuel.c"
  "Src/Application/Control/Control_Receive.c"
  "Src/Application/Control/Control_Redundancy.c"
  "Src/Application/Control/Control_Service.c"

  "Src/Application/DataStorage/DataStoreSpe.c"
  "Src/Application/DataStorage/DataStore.c"

  "Src/ISR/GPIOExIntISR.c"
  "Src/ISR/timersISR.c"

  "Src/Common/StartUpModeJudge.c"
  "Src/Common/CRC16.c"
  "Src/Common/cpuTest.c"
  "Src/Common/Common.c"
  "Src/Common/DSP2833x_usDelay.asm"

  "Src/OtherDriver/CommDRI_429.c"
  "Src/OtherDriver/SM25QH256M_SpiFlash.c"
  "Src/OtherDriver/CommDRI_422.c"
  "Src/OtherDriver/CommDRI_CAN.c"

  "Src/DSPDriver/DSP_DefaultIsr.c"
  "Src/DSPDriver/DSP_GPIO.c"
  "Src/DSPDriver/DSP_WDog.c"
  "Src/DSPDriver/DSP2833x_GlobalVariableDefs.c"
  "Src/DSPDriver/DSP_ADC.c"
  "Src/DSPDriver/DSP_Clock.c"
  "Src/DSPDriver/DSP_PieCtrl.c"
  "Src/DSPDriver/DSP_PieVect.c"
  "Src/DSPDriver/DSP_SCI.c"
  "Src/DSPDriver/DSP_SPI.c"
  "Src/DSPDriver/DSP_SYSCtrl.c"
  "Src/DSPDriver/DSP_Timer.c"
  "Src/DSPDriver/DSP_Xintf.c"
)

OBJ_FILES=()

echo "[INFO] Compiler: $CL2000"
echo "[INFO] Output dir: $OUT_DIR"
echo "[INFO] Sources: ${#SOURCES[@]}"

for src in "${SOURCES[@]}"; do
  src_path="$ROOT_DIR/$src"
  if [[ ! -f "$src_path" ]]; then
    echo "[ERR] missing source: $src"
    exit 2
  fi

  obj_name="${src//\//_}"
  obj_name="${obj_name%.*}.obj"
  obj_path="$OUT_DIR/obj/$obj_name"

  echo "[CC ] $src"
  "$CL2000" "${COMMON_FLAGS[@]}" "${INCLUDE_FLAGS[@]}" \
    --preproc_with_compile \
    --obj_directory="$OUT_DIR/obj" \
    --output_file="$obj_path" \
    -c "$src_path"

  OBJ_FILES+=("$obj_path")
done

echo "[LD ] $OUT_NAME.out"
"$CL2000" "${COMMON_FLAGS[@]}" \
  -z \
  -m"$OUT_DIR/$OUT_NAME.map" \
  --stack_size=0x700 --warn_sections \
  -i"$CCS_ROOT/lib" -i"$CCS_ROOT/include" \
  --reread_libs --xml_link_info="$OUT_DIR/${OUT_NAME}_linkInfo.xml" \
  --rom_model \
  -o "$OUT_DIR/$OUT_NAME.out" \
  "${OBJ_FILES[@]}" \
  "$ROOT_DIR/CMD/DSP2833x_Headers_nonBIOS.cmd" \
  "$ROOT_DIR/CMD/F28335.cmd" \
  -l"libc.a"

echo "[OK ] Built: $OUT_DIR/$OUT_NAME.out"
