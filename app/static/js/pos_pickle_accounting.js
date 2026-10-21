/**
 * pos_pickle_accounting.js
 * Tiện ích Quản trị Sân Pickleball, Điểm danh Hội viên, Sổ Quỹ Thu - Chi (Capex & Opex)
 * và Cấu hình Đồ uống kèm vé Social trên giao diện POS PiPo Garden.
 */

window.currentPosMode = 'restaurant';
let accountingCategories = null;

// Khởi chạy khi DOM sẵn sàng
document.addEventListener("DOMContentLoaded", () => {
  const urlParams = new URLSearchParams(window.location.search);
  const modeParam = urlParams.get('mode');
  if (modeParam === 'pickle') {
    setPosMode('pickle');
  }

  // Hook vào kiểm tra tài khoản
  setTimeout(checkAndApplyUserPosMode, 800);
});

function checkAndApplyUserPosMode() {
  if (window.currentUser) {
    if (window.currentUser.role === 'PICKLEBALL') {
      setPosMode('pickle');
      const toggleBtn = document.getElementById("btnPosModeToggle");
      if (toggleBtn) toggleBtn.classList.add("hidden"); // Khóa cố định ở chế độ Sân Pick
      
      const roleBadge = document.getElementById("userRoleBadge");
      if (roleBadge) roleBadge.innerText = "Sân Pickleball";
    }
  }
}

// =========================================================================
// 1. CHUYỂN ĐỔI CHẾ ĐỘ POS (NHÀ HÀNG vs SÂN PICKLEBALL)
// =========================================================================

function togglePosMode() {
  const newMode = (window.currentPosMode === 'pickle') ? 'restaurant' : 'pickle';
  setPosMode(newMode);
}

function setPosMode(mode) {
  window.currentPosMode = mode;
  const toggleBtnText = document.getElementById("posModeToggleText");
  const areaContainer = document.getElementById("areaFilterContainer");
  
  if (mode === 'pickle') {
    if (toggleBtnText) toggleBtnText.innerText = "Chế Độ Nhà Hàng";
    window.currentArea = 'Sân Pickle';
    
    // Đổi màu nút khu vực nếu có
    document.querySelectorAll(".area-btn").forEach(b => {
      b.className = "area-btn px-3 py-1.5 rounded-xl bg-white border border-stone-200 text-stone-600 text-xs font-bold hover:bg-stone-50";
    });
    const pickBtn = document.getElementById("areaBtn-Sân Pickle");
    if (pickBtn) pickBtn.className = "area-btn px-3 py-1.5 rounded-xl bg-emerald-800 text-white text-xs font-bold shadow-xs";

    showPosToast("🎾 Đã chuyển sang <b>Chế Độ Sân Pickleball</b> (Chỉ hiển thị 4 Sân & Menu Sân Pick)");
  } else {
    if (toggleBtnText) toggleBtnText.innerText = "Chế Độ Sân Pick";
    window.currentArea = 'ALL';

    document.querySelectorAll(".area-btn").forEach(b => {
      b.className = "area-btn px-3 py-1.5 rounded-xl bg-white border border-stone-200 text-stone-600 text-xs font-bold hover:bg-stone-50";
    });
    const allBtn = document.getElementById("areaBtn-ALL");
    if (allBtn) allBtn.className = "area-btn px-3 py-1.5 rounded-xl bg-stone-800 text-white text-xs font-bold shadow-xs";

    showPosToast("🍽️ Đã chuyển về <b>Chế Độ Toàn Nhà Hàng</b> (27 Bàn & Thực đơn đầy đủ)");
  }

  if (typeof renderTablesGrid === 'function') {
    renderTablesGrid();
  }
}

// =========================================================================
// 2. MODAL QUẢN LÝ HỘI VIÊN & ĐẶT SÂN CỐ ĐỊNH (PICKLEBALL MEMBERSHIPS)
// =========================================================================

let pickleMembershipsList = [];

function openPickleMembershipModal() {
  document.getElementById("pickleMembershipModal").classList.remove("hidden");
  switchPickleTab('checkin');
  loadTodayCheckins();
  loadPickleMemberships();
  initPickleRegisterForm();
}

function closePickleMembershipModal() {
  document.getElementById("pickleMembershipModal").classList.add("hidden");
}

function switchPickleTab(tab) {
  const tabs = ['checkin', 'register', 'list'];
  tabs.forEach(t => {
    const btn = document.getElementById(`pTabBtn-${t}`);
    const content = document.getElementById(`pTabContent-${t}`);
    if (t === tab) {
      if (btn) btn.className = "px-4 py-2.5 rounded-t-xl bg-white border-t-2 border-sky-600 text-sky-800 shadow-xs flex items-center gap-1.5 font-bold";
      if (content) content.classList.remove("hidden");
    } else {
      if (btn) btn.className = "px-4 py-2.5 rounded-t-xl text-stone-500 hover:text-stone-800 flex items-center gap-1.5 font-bold";
      if (content) content.classList.add("hidden");
    }
  });

  if (tab === 'list') {
    loadPickleMemberships();
  }
}

function initPickleRegisterForm() {
  const today = new Date().toISOString().split('T')[0];
  const startEl = document.getElementById("pRegStartDate");
  const endEl = document.getElementById("pRegEndDate");
  if (startEl && !startEl.value) startEl.value = today;
  
  if (endEl && !endEl.value) {
    const endDt = new Date();
    endDt.setDate(endDt.getDate() + 30);
    endEl.value = endDt.toISOString().split('T')[0];
  }

  onPickleTypeChange();
}

function onPickleTypeChange() {
  const type = document.getElementById("pRegType").value;
  const fixedBox = document.getElementById("pFixedCourtOptions");
  const priceInput = document.getElementById("pRegPrice");
  const paidInput = document.getElementById("pRegPaidAmount");
  const endEl = document.getElementById("pRegEndDate");

  const startDtStr = document.getElementById("pRegStartDate").value || new Date().toISOString().split('T')[0];
  const startDt = new Date(startDtStr);

  if (type === 'SOCIAL_MONTH_ALL') {
    if (fixedBox) fixedBox.classList.add("hidden");
    if (priceInput) priceInput.value = 1200000;
    if (paidInput) paidInput.value = 1200000;
    startDt.setDate(startDt.getDate() + 30);
    if (endEl) endEl.value = startDt.toISOString().split('T')[0];
  } else if (type === 'SOCIAL_MONTH_MORNING') {
    if (fixedBox) fixedBox.classList.add("hidden");
    if (priceInput) priceInput.value = 600000;
    if (paidInput) paidInput.value = 600000;
    startDt.setDate(startDt.getDate() + 30);
    if (endEl) endEl.value = startDt.toISOString().split('T')[0];
  } else if (type === 'SOCIAL_YEAR') {
    if (fixedBox) fixedBox.classList.add("hidden");
    if (priceInput) priceInput.value = 5000000;
    if (paidInput) paidInput.value = 5000000;
    startDt.setDate(startDt.getDate() + 365);
    if (endEl) endEl.value = startDt.toISOString().split('T')[0];
  } else if (type === 'FIXED_COURT_MONTHLY') {
    if (fixedBox) fixedBox.classList.remove("hidden");
    if (priceInput) priceInput.value = "";
    if (paidInput) paidInput.value = "";
    startDt.setDate(startDt.getDate() + 30);
    if (endEl) endEl.value = startDt.toISOString().split('T')[0];
  }
}

async function searchPickleMember() {
  const query = (document.getElementById("pCheckinSearchInput").value || "").trim();
  if (!query) {
    alert("Vui lòng nhập tên hoặc số điện thoại hội viên!");
    return;
  }

  try {
    const res = await fetch(`/api/pickleball/memberships?search=${encodeURIComponent(query)}&limit=10`);
    const data = await res.json();
    const resultBox = document.getElementById("pCheckinSearchResult");
    const cardsBox = document.getElementById("pCheckinCards");

    if (!data.memberships || data.memberships.length === 0) {
      cardsBox.innerHTML = `
        <div class="col-span-full p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 text-center">
          <i class="fa-solid fa-triangle-exclamation text-xl mb-1 text-amber-600"></i>
          <p class="font-bold">Không tìm thấy hội viên nào khớp với từ khóa "${query}".</p>
          <p class="text-[11px] mt-1 text-stone-500">Chuyển sang tab "Đăng Ký Gói Mới" để tạo thẻ hội viên cho khách.</p>
        </div>
      `;
      resultBox.classList.remove("hidden");
      return;
    }

    let html = "";
    data.memberships.forEach(m => {
      const isExpired = m.status === 'EXPIRED' || m.days_remaining < 0;
      const typeLabels = {
        SOCIAL_MONTH_ALL: "Social Tháng (Mọi Giờ)",
        SOCIAL_MONTH_MORNING: "Social Tháng (Sáng 06h-16h)",
        SOCIAL_YEAR: "Social Năm VIP (Cá Nhân)",
        FIXED_COURT_MONTHLY: "Cố Định Tháng"
      };

      html += `
        <div class="p-3.5 bg-white border ${isExpired ? 'border-rose-300 bg-rose-50/40' : 'border-sky-200 bg-sky-50/50'} rounded-2xl shadow-xs flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between">
              <span class="font-mono font-bold text-[10px] text-stone-500 bg-stone-200 px-2 py-0.5 rounded-md">${m.member_code}</span>
              <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${isExpired ? 'bg-rose-100 text-rose-700' : 'bg-emerald-100 text-emerald-800'}">
                ${isExpired ? 'Đã hết hạn' : `Còn ${m.days_remaining} ngày`}
              </span>
            </div>
            <div class="font-extrabold text-sm text-stone-900 mt-1">${m.customer_name}</div>
            <div class="text-stone-500 text-[11px]"><i class="fa-solid fa-phone text-stone-400"></i> ${m.phone}</div>
            <div class="text-sky-800 font-bold text-[11px] mt-1">🏸 ${typeLabels[m.membership_type] || m.membership_type}</div>
            ${m.time_slots_desc ? `<div class="text-[10px] text-stone-500">⏰ ${m.time_slots_desc} (Sân ${m.court_id || 'Chung'})</div>` : ''}
            <div class="text-[10px] text-stone-400 mt-1">Hạn: <b>${m.end_date}</b> • Đã chơi: <b>${m.checkin_count || 0} buổi</b></div>
          </div>
          <div class="mt-3 pt-2 border-t border-stone-200/60 flex gap-2">
            ${isExpired ? `
              <button type="button" onclick="renewPickleMembershipPrompt(${m.id}, '${m.customer_name}', '${m.membership_type}')" class="flex-1 py-1.5 bg-amber-600 hover:bg-amber-700 text-white rounded-xl font-bold text-xs flex items-center justify-center gap-1">
                <i class="fa-solid fa-rotate-right"></i> Gia Hạn Gói
              </button>
            ` : `
              <button type="button" onclick="executePickleCheckin(${m.id}, '${m.customer_name}')" class="flex-1 py-1.5 bg-emerald-700 hover:bg-emerald-800 active:scale-98 text-white rounded-xl font-extrabold text-xs flex items-center justify-center gap-1.5 shadow-sm">
                <i class="fa-solid fa-circle-check"></i> ĐIỂM DANH VÀO SÂN
              </button>
            `}
          </div>
        </div>
      `;
    });

    cardsBox.innerHTML = html;
    resultBox.classList.remove("hidden");
  } catch (err) {
    console.error("Lỗi tìm kiếm hội viên:", err);
    alert("Không thể tìm kiếm hội viên: " + err.message);
  }
}

async function executePickleCheckin(membershipId, customerName) {
  try {
    const res = await fetch(`/api/pickleball/memberships/${membershipId}/checkin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: "Check-in trực tiếp tại POS sân" })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Lỗi check-in");

    showPosToast(`✅ Check-in thành công cho <b>${customerName}</b>! (Lượt chơi thứ ${data.checkin_count})`);
    searchPickleMember();
    loadTodayCheckins();
  } catch (e) {
    alert("⚠️ " + e.message);
  }
}

async function loadTodayCheckins() {
  const box = document.getElementById("pTodayCheckinList");
  if (!box) return;

  try {
    const res = await fetch("/api/pickleball/checkins");
    const data = await res.json();
    if (!data.checkins || data.checkins.length === 0) {
      box.innerHTML = `<div class="p-3 text-center text-stone-400 italic">Chưa có lượt check-in nào trong ngày hôm nay.</div>`;
      return;
    }

    let html = "";
    data.checkins.forEach(c => {
      const timeStr = (c.checked_in_at || "").substring(11, 16);
      html += `
        <div class="py-2 px-1 flex items-center justify-between text-xs">
          <div>
            <span class="font-bold text-stone-800">${c.member_name}</span>
            <span class="text-stone-400 text-[10px] ml-1.5">(${c.phone})</span>
            <span class="ml-2 px-1.5 py-0.2 bg-sky-100 text-sky-800 rounded font-semibold text-[10px]">${c.member_code || 'MBR'}</span>
          </div>
          <div class="font-mono font-bold text-sky-700 text-xs">⏰ ${timeStr}</div>
        </div>
      `;
    });
    box.innerHTML = html;
  } catch (e) {
    console.warn("loadTodayCheckins error", e);
  }
}

async function submitPickleMembership(e) {
  e.preventDefault();
  const payload = {
    customer_name: document.getElementById("pRegName").value.trim(),
    phone: document.getElementById("pRegPhone").value.trim(),
    membership_type: document.getElementById("pRegType").value,
    court_id: parseInt(document.getElementById("pRegCourtId")?.value) || null,
    time_slots_desc: (document.getElementById("pRegSlotsDesc")?.value || "").trim(),
    start_date: document.getElementById("pRegStartDate").value,
    end_date: document.getElementById("pRegEndDate").value,
    price: parseInt(document.getElementById("pRegPrice").value) || 0,
    paid_amount: parseInt(document.getElementById("pRegPaidAmount").value) || 0,
    payment_method: document.getElementById("pRegPaymentMethod").value,
    notes: (document.getElementById("pRegNotes")?.value || "").trim()
  };

  try {
    const res = await fetch("/api/pickleball/memberships", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Lỗi tạo hội viên");

    showPosToast(`🎉 ${data.message}`);
    document.getElementById("pRegisterForm").reset();
    initPickleRegisterForm();
    switchPickleTab('list');
  } catch (err) {
    alert("⚠️ " + err.message);
  }
}

async function loadPickleMemberships() {
  const statusFilter = document.getElementById("pListStatusFilter")?.value || "ACTIVE";
  try {
    const res = await fetch(`/api/pickleball/memberships?status=${statusFilter}&limit=150`);
    const data = await res.json();
    pickleMembershipsList = data.memberships || [];

    const countEl = document.getElementById("pCountTotal");
    if (countEl) countEl.innerText = pickleMembershipsList.length;

    renderPickleMembersTable(pickleMembershipsList);
  } catch (e) {
    console.error("loadPickleMemberships error", e);
  }
}

function filterPickleMembersTable() {
  const search = (document.getElementById("pListSearchInput")?.value || "").trim().toLowerCase();
  const filtered = pickleMembershipsList.filter(m => 
    m.customer_name.toLowerCase().includes(search) ||
    m.phone.toLowerCase().includes(search) ||
    m.member_code.toLowerCase().includes(search)
  );
  renderPickleMembersTable(filtered);
}

function renderPickleMembersTable(list) {
  const tbody = document.getElementById("pMembersTableBody");
  if (!tbody) return;

  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="py-8 text-center text-stone-400">Không có hội viên nào.</td></tr>`;
    return;
  }

  const typeMap = {
    SOCIAL_MONTH_ALL: "Social Tháng (Mọi Giờ)",
    SOCIAL_MONTH_MORNING: "Social Tháng (Sáng)",
    SOCIAL_YEAR: "Social Năm VIP",
    FIXED_COURT_MONTHLY: "Cố Định Tháng"
  };

  let html = "";
  list.forEach(m => {
    const isExpired = m.status === 'EXPIRED' || m.days_remaining < 0;
    html += `
      <tr class="hover:bg-stone-50 transition">
        <td class="px-3 py-2.5 font-mono font-bold text-sky-800 text-[11px]">${m.member_code}</td>
        <td class="px-3 py-2.5">
          <div class="font-bold text-stone-800">${m.customer_name}</div>
          <div class="text-[10px] text-stone-400">${m.phone}</div>
        </td>
        <td class="px-3 py-2.5">
          <div class="font-semibold text-stone-700">${typeMap[m.membership_type] || m.membership_type}</div>
          ${m.time_slots_desc ? `<div class="text-[10px] text-stone-400">Sân ${m.court_id || '?'}: ${m.time_slots_desc}</div>` : ''}
        </td>
        <td class="px-3 py-2.5">
          <div class="font-bold ${isExpired ? 'text-rose-600' : 'text-stone-800'}">${m.end_date}</div>
          <div class="text-[10px] ${isExpired ? 'text-rose-500 font-bold' : (m.is_expiring_soon ? 'text-amber-600 font-bold' : 'text-emerald-700')}">
            ${isExpired ? 'Hết hạn' : `Còn ${m.days_remaining} ngày`}
          </div>
        </td>
        <td class="px-3 py-2.5 font-bold text-stone-700">${m.checkin_count || 0} lượt</td>
        <td class="px-3 py-2.5">
          <div class="font-extrabold text-stone-800">${(m.paid_amount || 0).toLocaleString()} đ</div>
          <span class="text-[10px] px-1.5 py-0.2 rounded font-bold ${m.payment_status === 'PAID' ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}">
            ${m.payment_status === 'PAID' ? 'Đã đủ' : 'Còn thiếu'}
          </span>
        </td>
        <td class="px-3 py-2.5 text-center">
          <button type="button" onclick="renewPickleMembershipPrompt(${m.id}, '${m.customer_name}', '${m.membership_type}')" class="px-2.5 py-1 rounded-lg bg-sky-700 hover:bg-sky-800 text-white font-bold text-[11px] transition shadow-xs">
            <i class="fa-solid fa-rotate-right"></i> Gia hạn
          </button>
        </td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

async function renewPickleMembershipPrompt(id, customerName, type) {
  const defaultFee = type === 'SOCIAL_YEAR' ? 5000000 : (type === 'SOCIAL_MONTH_MORNING' ? 600000 : 1200000);
  const feeStr = prompt(`Nhập số tiền thu để gia hạn thêm cho khách [${customerName}]:`, defaultFee);
  if (!feeStr) return;

  const fee = parseInt(feeStr);
  if (isNaN(fee) || fee <= 0) {
    alert("Số tiền không hợp lệ!");
    return;
  }

  const duration = (type === 'SOCIAL_YEAR') ? 12 : 1;
  try {
    const res = await fetch(`/api/pickleball/memberships/${id}/renew`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        duration_months: duration,
        amount_paid: fee,
        payment_method: "CASH"
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Lỗi gia hạn");

    showPosToast(`🎉 ${data.message}`);
    loadPickleMemberships();
    if (document.getElementById("pCheckinSearchResult") && !document.getElementById("pCheckinSearchResult").classList.contains("hidden")) {
      searchPickleMember();
    }
  } catch (err) {
    alert("⚠️ " + err.message);
  }
}

// =========================================================================
// 3. MODAL SỔ QUỸ THU - CHI (CAPEX & OPEX)
// =========================================================================

function openAccountingModal() {
  document.getElementById("accountingModal").classList.remove("hidden");
  switchAccountingTab('form');
  loadAccountingCategories();
  loadAccountingSummary();
  loadAccountingTransactions();
}

function closeAccountingModal() {
  document.getElementById("accountingModal").classList.add("hidden");
}

function switchAccountingTab(tab) {
  const btnForm = document.getElementById("accTabBtn-form");
  const btnHistory = document.getElementById("accTabBtn-history");
  const contentForm = document.getElementById("accountingForm");
  const contentHistory = document.getElementById("accTabContent-history");

  if (tab === 'form') {
    if (btnForm) btnForm.className = "px-4 py-2.5 rounded-t-xl bg-white border-t-2 border-emerald-700 text-emerald-900 shadow-xs flex items-center gap-1.5 font-bold";
    if (btnHistory) btnHistory.className = "px-4 py-2.5 rounded-t-xl text-stone-500 hover:text-stone-800 flex items-center gap-1.5 font-bold";
    if (contentForm) contentForm.classList.remove("hidden");
    if (contentHistory) contentHistory.classList.add("hidden");
  } else {
    if (btnHistory) btnHistory.className = "px-4 py-2.5 rounded-t-xl bg-white border-t-2 border-emerald-700 text-emerald-900 shadow-xs flex items-center gap-1.5 font-bold";
    if (btnForm) btnForm.className = "px-4 py-2.5 rounded-t-xl text-stone-500 hover:text-stone-800 flex items-center gap-1.5 font-bold";
    if (contentHistory) contentHistory.classList.remove("hidden");
    if (contentForm) contentForm.classList.add("hidden");
    loadAccountingTransactions();
    loadAccountingSummary();
  }
}

async function loadAccountingCategories() {
  if (accountingCategories) {
    onAccTransTypeChange();
    return;
  }
  try {
    const res = await fetch("/api/accounting/categories");
    const data = await res.json();
    accountingCategories = data.categories;
    onAccTransTypeChange();
  } catch (e) {
    console.error("loadAccountingCategories error", e);
  }
}

function onAccTransTypeChange() {
  const transType = document.getElementById("accTransType").value;
  const costCatEl = document.getElementById("accCostCategory");
  const expTypeSelect = document.getElementById("accExpenseType");
  if (!accountingCategories || !expTypeSelect) return;

  if (transType === 'INCOME') {
    if (costCatEl) costCatEl.disabled = true;
    let html = "";
    (accountingCategories.INCOME || []).forEach(c => {
      html += `<option value="${c.code}">${c.icon} ${c.name}</option>`;
    });
    expTypeSelect.innerHTML = html;
  } else {
    if (costCatEl) costCatEl.disabled = false;
    const cat = (costCatEl?.value || "OPEX");
    const list = accountingCategories[cat] || accountingCategories.OPEX || [];
    let html = "";
    list.forEach(c => {
      html += `<option value="${c.code}">${c.icon} ${c.name}</option>`;
    });
    expTypeSelect.innerHTML = html;
  }
}

document.getElementById("accCostCategory")?.addEventListener("change", onAccTransTypeChange);

async function submitAccountingTransaction(e) {
  e.preventDefault();
  const payload = {
    transaction_type: document.getElementById("accTransType").value,
    cost_category: document.getElementById("accCostCategory").value,
    department: document.getElementById("accDepartment").value,
    expense_type: document.getElementById("accExpenseType").value,
    amount: parseInt(document.getElementById("accAmount").value) || 0,
    payment_method: document.getElementById("accPaymentMethod").value,
    recipient_payer: (document.getElementById("accRecipientPayer")?.value || "").trim(),
    description: document.getElementById("accDescription").value.trim()
  };

  try {
    const res = await fetch("/api/accounting/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Lỗi ghi sổ quỹ");

    showPosToast(`✅ ${data.message}`);
    document.getElementById("accountingForm").reset();
    onAccTransTypeChange();
    switchAccountingTab('history');
  } catch (err) {
    alert("⚠️ " + err.message);
  }
}

async function loadAccountingSummary() {
  try {
    const res = await fetch("/api/accounting/summary-today");
    const data = await res.json();
    if (!res.ok) return;

    if (document.getElementById("accKpiPos")) document.getElementById("accKpiPos").innerText = (data.revenue_today || 0).toLocaleString() + " đ";
    if (document.getElementById("accKpiOpex")) document.getElementById("accKpiOpex").innerText = (data.opex_today || 0).toLocaleString() + " đ";
    if (document.getElementById("accKpiCapex")) document.getElementById("accKpiCapex").innerText = (data.capex_today || 0).toLocaleString() + " đ";
    if (document.getElementById("accKpiDrawer")) document.getElementById("accKpiDrawer").innerText = (data.estimated_cash_drawer || 0).toLocaleString() + " đ";
  } catch (e) {
    console.warn("loadAccountingSummary error", e);
  }
}

async function loadAccountingTransactions() {
  const tbody = document.getElementById("accTransactionsTableBody");
  if (!tbody) return;

  try {
    const today = new Date().toISOString().split('T')[0];
    const res = await fetch(`/api/accounting/transactions?from_date=${today}&to_date=${today}&limit=50`);
    const data = await res.json();
    const rows = data.transactions || [];

    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="py-6 text-center text-stone-400 italic">Chưa có giao dịch thu chi nào trong ngày hôm nay.</td></tr>`;
      return;
    }

    let html = "";
    rows.forEach(r => {
      const isExp = r.transaction_type === 'EXPENSE';
      html += `
        <tr class="hover:bg-stone-50">
          <td class="px-3 py-2 font-mono font-bold text-stone-700 text-[11px]">${r.transaction_code}</td>
          <td class="px-3 py-2 font-bold ${isExp ? 'text-rose-600' : 'text-emerald-700'}">
            ${isExp ? 'CHI (' + r.cost_category + ')' : 'THU'}
          </td>
          <td class="px-3 py-2 text-[11px] text-stone-600">${r.expense_type}</td>
          <td class="px-3 py-2 font-extrabold ${isExp ? 'text-rose-700' : 'text-emerald-800'}">
            ${isExp ? '-' : '+'}${r.amount.toLocaleString()} đ
          </td>
          <td class="px-3 py-2 text-[11px] text-stone-700">${r.recipient_payer || '-'}</td>
          <td class="px-3 py-2 text-[11px] text-stone-600">${r.description}</td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  } catch (e) {
    console.warn("loadAccountingTransactions error", e);
  }
}

// =========================================================================
// 4. MODAL CẤU HÌNH ĐỒ UỐNG KÈM VÉ SOCIAL (60K KÈM NƯỚC)
// =========================================================================

function openSocialDrinkModal() {
  document.getElementById("socialDrinkModal").classList.remove("hidden");
  loadSocialDrinkConfig();
}

function closeSocialDrinkModal() {
  document.getElementById("socialDrinkModal").classList.add("hidden");
}

async function loadSocialDrinkConfig() {
  try {
    const res = await fetch("/api/pickleball/settings/social-drink");
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    const currEl = document.getElementById("currentSocialDrinkName");
    if (currEl) {
      currEl.innerText = `${data.current_drink.name} (Giá bán: ${data.current_drink.price.toLocaleString()} đ)`;
    }

    const select = document.getElementById("selectSocialDrink");
    if (select) {
      let html = "";
      (data.available_drinks || []).forEach(d => {
        const isSel = d.id == data.included_drink_id ? "selected" : "";
        html += `<option value="${d.id}" ${isSel}>${d.name} (${d.price.toLocaleString()} đ) • ${d.category_name || 'Đồ uống'}</option>`;
      });
      select.innerHTML = html;
    }
  } catch (e) {
    console.error("loadSocialDrinkConfig error", e);
  }
}

async function saveSocialDrinkConfig() {
  const select = document.getElementById("selectSocialDrink");
  const drinkId = parseInt(select.value);
  if (!drinkId) return;

  try {
    const res = await fetch("/api/pickleball/settings/social-drink", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drink_item_id: drinkId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Lỗi lưu cấu hình");

    showPosToast(`🥤 ${data.message}`);
    closeSocialDrinkModal();
  } catch (err) {
    alert("⚠️ " + err.message);
  }
}
