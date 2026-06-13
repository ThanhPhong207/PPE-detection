package ppe.ppedetectuser.entities.response;

import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class ResponseData<T> {
    private String statusCode;
    private String message;
    private T data;
}
