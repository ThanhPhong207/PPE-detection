package ppe.ppedetectuser.exception;

import lombok.Getter;

@Getter
public enum AppErrorCode {
    SUCCESS("200", "Success"),
    ERROR("500", "Error");

    private final String code;
    private final String message;

    AppErrorCode(String code, String message) {
        this.code = code;
        this.message = message;
    }
}
