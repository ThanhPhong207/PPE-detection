package ppe.ppedetectuser.entities.DTO;

import lombok.*;
import ppe.ppedetectuser.entities.enums.UserRole;
import java.time.LocalDateTime;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class UsersDTO {
    private Long id;
    private String email;
    private String fullName;
    private String avatarUrl;
    private String googleId;
    private UserRole role;
    private boolean active;
    private LocalDateTime createdAt;
    private LocalDateTime lastLogin;
}
