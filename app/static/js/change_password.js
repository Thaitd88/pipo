/**
 * change_password.js
 * Quản lý đổi mật khẩu cá nhân cho mọi người dùng đã đăng nhập (Admin, Thu ngân, Sân Pick, Bếp, Phục vụ).
 */

function openChangePasswordModal() {
  const modal = document.getElementById("changePasswordModal");
  if (!modal) return;
  document.getElementById("changePasswordForm")?.reset();
  const errMsg = document.getElementById("cpErrorMsg");
  if (errMsg) errMsg.classList.add("hidden");
  modal.classList.remove("hidden");
  setTimeout(() => document.getElementById("cpCurrentPassword")?.focus(), 100);
}

function closeChangePasswordModal() {
  document.getElementById("changePasswordModal")?.classList.add("hidden");
}

function togglePasswordVisibility(inputId, btn) {
  const inp = document.getElementById(inputId);
  if (!inp) return;
  const isPwd = inp.type === "password";
  inp.type = isPwd ? "text" : "password";
  const icon = btn.querySelector("i");
  if (icon) {
    icon.className = isPwd ? "fa-solid fa-eye-slash text-xs" : "fa-solid fa-eye text-xs";
  }
}

async function submitChangePassword(e) {
  if (e) e.preventDefault();
  const curr = document.getElementById("cpCurrentPassword")?.value || "";
  const newPwd = document.getElementById("cpNewPassword")?.value || "";
  const conf = document.getElementById("cpConfirmPassword")?.value || "";
  const errEl = document.getElementById("cpErrorMsg");
  const btn = document.getElementById("cpSubmitBtn");

  if (!curr) {
    showCpError("Vui lòng nhập mật khẩu hiện tại!");
    return;
  }
  if (!newPwd || newPwd.length < 6) {
    showCpError("Mật khẩu mới phải có tối thiểu 6 ký tự!");
    return;
  }
  if (newPwd !== conf) {
    showCpError("Xác nhận mật khẩu mới không khớp!");
    return;
  }
  if (curr === newPwd) {
    showCpError("Mật khẩu mới không được trùng với mật khẩu cũ!");
    return;
  }

  if (errEl) errEl.classList.add("hidden");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang lưu...`;
  }

  try {
    const res = await fetch("/api/auth/change-password", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: curr,
        new_password: newPwd,
        confirm_password: conf
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Đổi mật khẩu thất bại");

    alert(`🎉 ${data.message}`);
    closeChangePasswordModal();
  } catch (err) {
    showCpError(err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<i class="fa-solid fa-floppy-disk"></i> Cập Nhật Mật Khẩu`;
    }
  }
}

function showCpError(msg) {
  const errEl = document.getElementById("cpErrorMsg");
  if (errEl) {
    errEl.innerText = msg;
    errEl.classList.remove("hidden");
  } else {
    alert(msg);
  }
}
