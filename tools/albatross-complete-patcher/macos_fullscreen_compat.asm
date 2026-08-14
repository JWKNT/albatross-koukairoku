BITS 32
ORG 0x472c30

; CrossOver/macOS exposes no 800x600 display mode. Report success so the
; engine enters its fullscreen popup path without changing the display mode.
fake_change_display_settings:
    xor eax, eax
    ret 8

; Replace the engine's zero-size SWP_NOSIZE fullscreen request with the
; largest centered 4:3 window that fits the current desktop.
fullscreen_set_window_pos:
    cmp dword [esp + 28], 0x21
    jne .passthrough
    cmp dword [esp + 20], 0
    jne .passthrough
    cmp dword [esp + 24], 0
    jne .passthrough

    push ebp
    mov ebp, esp
    sub esp, 24
    push ebx
    push esi
    push edi

    call dword [0x47320c]       ; GetDesktopWindow
    lea ecx, [ebp - 16]
    push ecx
    push eax
    call dword [0x473208]       ; GetWindowRect
    test eax, eax
    jz .fullscreen_failed

    mov ebx, [ebp - 8]
    sub ebx, [ebp - 16]         ; desktop width
    mov esi, [ebp - 4]
    sub esi, [ebp - 12]         ; desktop height
    mov eax, ebx
    imul eax, eax, 3
    mov ecx, esi
    shl ecx, 2
    cmp eax, ecx
    jle .width_limited

    mov eax, esi
    xor edx, edx
    mov ecx, 3
    div ecx
    shl eax, 2
    mov edi, eax
    mov eax, esi
    jmp .geometry_ready

.width_limited:
    mov edi, ebx
    mov eax, ebx
    imul eax, eax, 3
    shr eax, 2

.geometry_ready:
    mov [ebp - 20], edi
    mov [ebp - 24], eax
    mov ecx, ebx
    sub ecx, edi
    sar ecx, 1
    add ecx, [ebp - 16]
    mov edx, esi
    sub edx, eax
    sar edx, 1
    add edx, [ebp - 12]

    push dword 0x60             ; SWP_FRAMECHANGED | SWP_SHOWWINDOW
    push dword [ebp - 24]
    push dword [ebp - 20]
    push edx
    push ecx
    push dword [ebp + 12]
    push dword [ebp + 8]
    call dword [0x473210]       ; SetWindowPos
    jmp .fullscreen_done

.fullscreen_failed:
    xor eax, eax

.fullscreen_done:
    pop edi
    pop esi
    pop ebx
    mov esp, ebp
    pop ebp
    ret 28

.passthrough:
    jmp dword [0x473210]
