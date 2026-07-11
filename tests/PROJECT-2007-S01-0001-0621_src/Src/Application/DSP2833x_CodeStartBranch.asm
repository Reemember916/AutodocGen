; APP-only startup entry.
; The device still enters FLASHA first via a separate boot stub, then jumps
; to APPBEGIN in FLASHB. This project only owns the app entry.

WD_DISABLE  .set    1

    .ref _c_int00
    .global app_code_start

    .sect "appcodestart"

app_code_start:
    LB start_branch

    .text
start_branch:
    .if WD_DISABLE == 1
        LB wd_disable
    .else
        LB _c_int00
    .endif

    .if WD_DISABLE == 1
wd_disable:
    SETC OBJMODE
    EALLOW
    MOVZ DP, #7029h>>6
    MOV @7029h, #0068h
    EDIS
    LB _c_int00
    .endif

    .end
