/**
 * admin_pickle_accounting.js
 * Quản trị Sân Pickleball, Hội Viên và Kế Toán Lãi Lỗ (P&L) trên trang Admin PiPo Garden.
 */

// =========================================================================
// 1. SÂN PICKLEBALL & HỘI VIÊN (ADMIN)
// =========================================================================

let adminPickleMembers = [];

async function loadAdminPickleball() {
  loadAdminMemberships();
  loadAdminCheckins();
  loadAdminSocialDrink();
}

async function loadAdminMemberships() {
  const statusFilter = document.getElementById("admPickleStatusFilter")?.value || "ALL";
  try {
    const res = await fetch(`/api/pickleball/memberships?status=${statusFilter}&limit=200`);
    const data = await res.json();
    adminPickleMembers = data.memberships || [];

    // Cập nhật thẻ thống kê
    const total = adminPickleMembers.length;
    const active = adminPickleMembers.filter(m => m.status === 'ACTIVE' && m.days_remaining >= 0).length;
    const expiring = adminPickleMembers.filter(m => m.is_expiring_soon).length;
    const expired = adminPickleMembers.filter(m => m.status === 'EXPIRED' || m.days_remaining < 0).length;

    if (document.getElementById("admPStatTotal")) document.getElementById("admPStatTotal").innerText = total;
    if (document.getElementById("admPStatActive")) document.getElementById("admPStatActive").innerText = active;
    if (document.getElementById("admPStatExpiring")) document.getElementById("admPStatExpiring").innerText = expiring;
    if (document.getElementById("admPStatExpired")) document.getElementById("admPStatExpired").innerText = expired;

    renderAdminMembershipsTable(adminPickleMembers);
  } catch (e) {
    console.error("loadAdminMemberships error", e);
  }
}

function filterAdminMembersTable() {
  const q = (document.getElementById("admPickleSearchInput")?.value || "").trim().toLowerCase();
  const filtered = adminPickleMembers.filter(m =>
    m.customer_name.toLowerCase().includes(q) ||
    m.phone.toLowerCase().includes(q) ||
    m.member_code.toLowerCase().includes(q)
  );
  renderAdminMembershipsTable(filtered);
}

function renderAdminMembershipsTable(list) {
  const tbody = document.getElementById("admPickleMembersTableBody");
  if (!tbody) return;

  if (list.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" class="py-10 text-center text-stone-400 font-medium">Chưa có dữ liệu hội viên phù hợp.</td></tr>`;
    return;
  }

  const typeLabels = {
    SOCIAL_MONTH_ALL: "Social Tháng (Mọi Giờ)",
    SOCIAL_MONTH_MORNING: "Social Tháng (Sáng 06h-16h)",
    SOCIAL_YEAR: "Social Năm VIP (Cá Nhân)",
    FIXED_COURT_MONTHLY: "Cố Định Tháng"
  };

  let html = "";
  list.forEach(m => {
    const isExpired = m.status === 'EXPIRED' || m.days_remaining < 0;
    html += `
      <tr class="hover:bg-stone-50 transition border-b border-stone-100">
        <td class="px-3.5 py-3 font-mono font-bold text-sky-800 text-xs">${m.member_code}</td>
        <td class="px-3.5 py-3">
          <div class="font-extrabold text-stone-900">${m.customer_name}</div>
          <div class="text-[11px] text-stone-400"><i class="fa-solid fa-phone text-stone-300"></i> ${m.phone}</div>
        </td>
        <td class="px-3.5 py-3">
          <span class="font-semibold text-stone-700">${typeLabels[m.membership_type] || m.membership_type}</span>
          ${m.time_slots_desc ? `<div class="text-[10px] text-sky-700 font-medium mt-0.5">Sân ${m.court_id || 'Chung'}: ${m.time_slots_desc}</div>` : ''}
        </td>
        <td class="px-3.5 py-3 text-xs">
          <div class="text-stone-500 font-medium">${m.start_date}</div>
          <div class="font-bold ${isExpired ? 'text-rose-600' : 'text-stone-800'}">${m.end_date}</div>
        </td>
        <td class="px-3.5 py-3">
          <span class="px-2.5 py-0.5 rounded-full text-[10px] font-bold ${isExpired ? 'bg-rose-100 text-rose-700' : (m.is_expiring_soon ? 'bg-amber-100 text-amber-800 animate-pulse' : 'bg-emerald-100 text-emerald-800')}">
            ${isExpired ? 'Đã hết hạn' : `Còn ${m.days_remaining} ngày`}
          </span>
        </td>
        <td class="px-3.5 py-3 font-extrabold text-stone-700 text-xs text-center">${m.checkin_count || 0} buổi</td>
        <td class="px-3.5 py-3 text-xs">
          <div class="font-black text-stone-900">${(m.paid_amount || 0).toLocaleString()} đ</div>
          <span class="text-[10px] font-bold ${m.payment_status === 'PAID' ? 'text-emerald-700' : 'text-amber-600'}">
            ${m.payment_status === 'PAID' ? '✓ Đã thu đủ' : 'Còn nợ'}
          </span>
        </td>
        <td class="px-3.5 py-3 text-center">
          <div class="flex items-center justify-center gap-1.5">
            <button type="button" onclick="renewAdminMemberPrompt(${m.id}, '${m.customer_name}', '${m.membership_type}')" class="px-2.5 py-1 rounded-lg bg-sky-700 hover:bg-sky-800 text-white font-bold text-xs shadow-xs transition flex items-center gap-1">
              <i class="fa-solid fa-rotate-right"></i> Gia hạn
            </button>
            <button type="button" onclick="executeAdminCheckin(${m.id}, '${m.customer_name}')" class="px-2 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shadow-xs transition" title="Điểm danh check-in">
              <i class="fa-solid fa-circle-check"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  });
  tbody.innerHTML = html;
}

async function executeAdminCheckin(id, name) {
  try {
    const res = await fetch(`/api/pickleball/memberships/${id}/checkin`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes: "Check-in từ trang Quản trị Admin" })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    alert(`✅ Check-in thành công cho [${name}]! Lượt chơi thứ ${data.checkin_count}.`);
    loadAdminMemberships();
    loadAdminCheckins();
  } catch (err) {
    alert("⚠️ " + err.message);
  }
}

async function renewAdminMemberPrompt(id, name, type) {
  const defaultFee = type === 'SOCIAL_YEAR' ? 5000000 : (type === 'SOCIAL_MONTH_MORNING' ? 600000 : 1200000);
  const feeStr = prompt(`Nhập số tiền thu để gia hạn cho hội viên [${name}]:`, defaultFee);
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
    if (!res.ok) throw new Error(data.detail);

    alert(`🎉 ${data.message}`);
    loadAdminMemberships();
  } catch (e) {
    alert("⚠️ " + e.message);
  }
}

async function loadAdminCheckins() {
  const container = document.getElementById("admPickleTodayCheckins");
  if (!container) return;

  try {
    const res = await fetch("/api/pickleball/checkins");
    const data = await res.json();
    if (!data.checkins || data.checkins.length === 0) {
      container.innerHTML = `<div class="p-4 text-center text-stone-400 italic text-xs">Chưa có lượt check-in nào trong ngày hôm nay.</div>`;
      return;
    }

    let html = "";
    data.checkins.forEach(c => {
      const timeStr = (c.checked_in_at || "").substring(11, 16);
      html += `
        <div class="p-2.5 bg-stone-50 rounded-xl border border-stone-200/80 flex items-center justify-between text-xs">
          <div>
            <span class="font-bold text-stone-900">${c.member_name}</span>
            <span class="text-stone-400 text-[10px] ml-1">(${c.phone})</span>
            <span class="ml-1.5 px-1.5 py-0.2 bg-sky-100 text-sky-800 font-bold rounded text-[10px]">${c.member_code || 'MBR'}</span>
          </div>
          <span class="font-mono font-bold text-sky-700">⏰ ${timeStr}</span>
        </div>
      `;
    });
    container.innerHTML = html;
  } catch (e) {
    console.warn("loadAdminCheckins error", e);
  }
}

async function loadAdminSocialDrink() {
  try {
    const res = await fetch("/api/pickleball/settings/social-drink");
    const data = await res.json();
    if (!res.ok) return;

    const currName = document.getElementById("admCurrentSocialDrink");
    if (currName) {
      currName.innerText = `${data.current_drink.name} (${data.current_drink.price.toLocaleString()} đ)`;
    }

    const select = document.getElementById("admSelectSocialDrink");
    if (select) {
      let html = "";
      (data.available_drinks || []).forEach(d => {
        const isSel = d.id == data.included_drink_id ? "selected" : "";
        html += `<option value="${d.id}" ${isSel}>${d.name} (${d.price.toLocaleString()} đ)</option>`;
      });
      select.innerHTML = html;
    }
  } catch (e) {
    console.warn("loadAdminSocialDrink error", e);
  }
}

async function saveAdminSocialDrink() {
  const select = document.getElementById("admSelectSocialDrink");
  const drinkId = parseInt(select.value);
  if (!drinkId) return;

  try {
    const res = await fetch("/api/pickleball/settings/social-drink", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ drink_item_id: drinkId })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    alert(`✅ ${data.message}`);
    loadAdminSocialDrink();
  } catch (err) {
    alert("⚠️ " + err.message);
  }
}


// =========================================================================
// 2. KẾ TOÁN & BÁO CÁO LÃI LỖ (P&L - CAPEX & OPEX)
// =========================================================================

async function loadAdminAccounting() {
  initAccountingDateFilters();
  loadAccountingPnL();
  loadAccountingLedger();
}

function initAccountingDateFilters() {
  const fromEl = document.getElementById("pnlFromDate");
  const toEl = document.getElementById("pnlToDate");
  const today = new Date().toISOString().split('T')[0];

  if (toEl && !toEl.value) toEl.value = today;
  if (fromEl && !fromEl.value) {
    // Đầu tháng hiện tại
    const dt = new Date();
    dt.setDate(1);
    fromEl.value = dt.toISOString().split('T')[0];
  }
}

function setPnlQuickPeriod(period) {
  const fromEl = document.getElementById("pnlFromDate");
  const toEl = document.getElementById("pnlToDate");
  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];

  if (period === 'today') {
    fromEl.value = todayStr;
    toEl.value = todayStr;
  } else if (period === 'this_week') {
    const d = new Date();
    const day = d.getDay();
    const diff = d.getDate() - day + (day === 0 ? -6 : 1); // Thứ 2
    d.setDate(diff);
    fromEl.value = d.toISOString().split('T')[0];
    toEl.value = todayStr;
  } else if (period === 'this_month') {
    const d = new Date();
    d.setDate(1);
    fromEl.value = d.toISOString().split('T')[0];
    toEl.value = todayStr;
  } else if (period === 'last_month') {
    const d1 = new Date();
    d1.setMonth(d1.getMonth() - 1);
    d1.setDate(1);
    const d2 = new Date();
    d2.setDate(0); // Ngày cuối tháng trước
    fromEl.value = d1.toISOString().split('T')[0];
    toEl.value = d2.toISOString().split('T')[0];
  }

  loadAccountingPnL();
  loadAccountingLedger();
}

async function loadAccountingPnL() {
  const fromDate = document.getElementById("pnlFromDate")?.value || "";
  const toDate = document.getElementById("pnlToDate")?.value || "";
  const dept = document.getElementById("pnlDepartmentFilter")?.value || "ALL";

  try {
    const res = await fetch(`/api/accounting/pnl?from_date=${fromDate}&to_date=${toDate}&department=${dept}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    // Điền thẻ KPI
    const rev = data.revenue;
    const cogs = data.cost_of_goods_sold;
    const opex = data.operating_expenses_opex;
    const ebitda = data.operating_profit_ebitda;
    const capex = data.capital_expenditures_capex;
    const cashflow = data.net_cashflow;

    if (document.getElementById("pnlKpiTotalRev")) document.getElementById("pnlKpiTotalRev").innerText = (rev.total_revenue || 0).toLocaleString() + " đ";
    if (document.getElementById("pnlKpiFbRev")) document.getElementById("pnlKpiFbRev").innerText = (rev.fb_restaurant || 0).toLocaleString() + " đ";
    if (document.getElementById("pnlKpiPickleRev")) document.getElementById("pnlKpiPickleRev").innerText = (rev.pickleball_total || 0).toLocaleString() + " đ";
    if (document.getElementById("pnlKpiOtherInc")) document.getElementById("pnlKpiOtherInc").innerText = (rev.other_income || 0).toLocaleString() + " đ";

    if (document.getElementById("pnlKpiCogs")) document.getElementById("pnlKpiCogs").innerText = (cogs.cogs_total || 0).toLocaleString() + " đ";
    if (document.getElementById("pnlKpiGrossProfit")) document.getElementById("pnlKpiGrossProfit").innerText = (cogs.gross_profit || 0).toLocaleString() + " đ";
    if (document.getElementById("pnlKpiGrossMargin")) document.getElementById("pnlKpiGrossMargin").innerText = `${cogs.gross_margin_percent}%`;

    if (document.getElementById("pnlKpiOpex")) document.getElementById("pnlKpiOpex").innerText = (opex.total_opex || 0).toLocaleString() + " đ";
    if (document.getElementById("pnlKpiEbitda")) document.getElementById("pnlKpiEbitda").innerText = (ebitda.amount || 0).toLocaleString() + " đ";
    if (document.getElementById("pnlKpiEbitdaMargin")) document.getElementById("pnlKpiEbitdaMargin").innerText = `${ebitda.margin_percent}%`;

    if (document.getElementById("pnlKpiCapex")) document.getElementById("pnlKpiCapex").innerText = (capex.total_capex || 0).toLocaleString() + " đ";
    if (document.getElementById("pnlKpiNetCashflow")) document.getElementById("pnlKpiNetCashflow").innerText = (cashflow.amount || 0).toLocaleString() + " đ";

    // Chi tiết phân bổ OPEX & CAPEX
    renderExpensesBreakdown(opex.breakdown || {}, capex.breakdown || {});
  } catch (err) {
    console.error("loadAccountingPnL error", err);
  }
}

function renderExpensesBreakdown(opexMap, capexMap) {
  const opexBox = document.getElementById("pnlOpexBreakdown");
  const capexBox = document.getElementById("pnlCapexBreakdown");

  if (opexBox) {
    const opexKeys = Object.keys(opexMap);
    if (opexKeys.length === 0) {
      opexBox.innerHTML = `<div class="p-3 text-stone-400 italic text-xs">Chưa phát sinh chi phí vận hành trong kỳ này.</div>`;
    } else {
      let html = "";
      opexKeys.forEach(k => {
        html += `
          <div class="flex items-center justify-between py-2 border-b border-stone-100 text-xs">
            <span class="font-medium text-stone-700">${k}</span>
            <span class="font-bold text-amber-700">${(opexMap[k] || 0).toLocaleString()} đ</span>
          </div>
        `;
      });
      opexBox.innerHTML = html;
    }
  }

  if (capexBox) {
    const capexKeys = Object.keys(capexMap);
    if (capexKeys.length === 0) {
      capexBox.innerHTML = `<div class="p-3 text-stone-400 italic text-xs">Chưa phát sinh đầu tư tài sản trong kỳ này.</div>`;
    } else {
      let html = "";
      capexKeys.forEach(k => {
        html += `
          <div class="flex items-center justify-between py-2 border-b border-stone-100 text-xs">
            <span class="font-medium text-stone-700">${k}</span>
            <span class="font-bold text-purple-700">${(capexMap[k] || 0).toLocaleString()} đ</span>
          </div>
        `;
      });
      capexBox.innerHTML = html;
    }
  }
}

async function loadAccountingLedger() {
  const fromDate = document.getElementById("pnlFromDate")?.value || "";
  const toDate = document.getElementById("pnlToDate")?.value || "";
  const dept = document.getElementById("pnlDepartmentFilter")?.value || "ALL";

  const tbody = document.getElementById("admTransactionsTableBody");
  if (!tbody) return;

  try {
    const res = await fetch(`/api/accounting/transactions?from_date=${fromDate}&to_date=${toDate}&department=${dept}&limit=200`);
    const data = await res.json();
    const rows = data.transactions || [];

    if (rows.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" class="py-10 text-center text-stone-400 font-medium">Không có phiếu thu chi nào trong kỳ này.</td></tr>`;
      return;
    }

    let html = "";
    rows.forEach(r => {
      const isExp = r.transaction_type === 'EXPENSE';
      const deptLabels = { RESTAURANT: "Nhà Hàng", PICKLEBALL: "Sân Pickle", GENERAL: "Chung" };
      html += `
        <tr class="hover:bg-stone-50 transition border-b border-stone-100">
          <td class="px-3.5 py-3 font-mono font-bold text-stone-800 text-xs">${r.transaction_code}</td>
          <td class="px-3.5 py-3">
            <span class="px-2 py-0.5 rounded-full text-[10px] font-bold ${isExp ? 'bg-rose-100 text-rose-800' : 'bg-emerald-100 text-emerald-800'}">
              ${isExp ? 'CHI (' + r.cost_category + ')' : 'THU'}
            </span>
            <span class="px-1.5 py-0.5 rounded text-[9.5px] font-bold ${((r.payment_method || 'CASH').toUpperCase() === 'CASH') ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' : 'bg-blue-50 text-blue-700 border border-blue-200'} ml-1">
              ${((r.payment_method || 'CASH').toUpperCase() === 'CASH') ? '💵 TM' : '📲 CK'}
            </span>
          </td>
          <td class="px-3.5 py-3">
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-stone-100 text-stone-700">
              ${deptLabels[r.department] || r.department}
            </span>
          </td>
          <td class="px-3.5 py-3 text-xs font-semibold text-stone-700">${r.expense_type}</td>
          <td class="px-3.5 py-3 font-black text-xs ${isExp ? 'text-rose-700' : 'text-emerald-800'}">
            ${isExp ? '-' : '+'}${r.amount.toLocaleString()} đ
          </td>
          <td class="px-3.5 py-3 text-xs text-stone-700">${r.recipient_payer || '-'}</td>
          <td class="px-3.5 py-3 text-xs text-stone-600 max-w-xs">
            <div class="truncate" title="${r.description}">${r.description}</div>
            ${r.receipt_url ? `
              <button type="button" onclick="zoomReceiptImage('${r.receipt_url}')" class="mt-1 px-2 py-0.5 rounded bg-emerald-50 hover:bg-emerald-100 text-emerald-800 font-bold text-[10px] inline-flex items-center gap-1 border border-emerald-200 cursor-pointer shadow-2xs">
                <i class="fa-solid fa-image text-emerald-600"></i> Xem chứng từ
              </button>
            ` : ''}
          </td>
          <td class="px-3.5 py-3 text-center">
            <button type="button" onclick="deleteAdminTransaction(${r.id}, '${r.transaction_code}')" class="w-7 h-7 rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-700 transition" title="Xóa phiếu">
              <i class="fa-solid fa-trash-can text-xs"></i>
            </button>
          </td>
        </tr>
      `;
    });
    tbody.innerHTML = html;
  } catch (e) {
    console.error("loadAccountingLedger error", e);
  }
}

async function deleteAdminTransaction(id, code) {
  if (!confirm(`Bạn có chắc chắn muốn xóa phiếu [${code}] khỏi sổ quỹ? Thao tác này không thể hoàn tác.`)) {
    return;
  }
  try {
    const res = await fetch(`/api/accounting/transactions/${id}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    alert(`✅ ${data.message}`);
    loadAccountingPnL();
    loadAccountingLedger();
  } catch (err) {
    alert("⚠️ " + err.message);
  }
}


async function deleteAdminMember(id, name) {
  if (!confirm(`Bạn có chắc chắn muốn xóa thẻ hội viên của [${name}]? Lịch sử check-in liên quan cũng sẽ bị gỡ bỏ.`)) return;
  try {
    const res = await fetch(`/api/pickleball/memberships/${id}`, { method: "DELETE" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);
    alert(`✅ ${data.message}`);
    loadAdminMemberships();
    loadAdminCheckins();
  } catch (err) {
    alert("⚠️ " + err.message);
  }
}

function openAdminAddMemberModal() {
  const modal = document.getElementById("adminAddMemberModal");
  if (modal) modal.classList.remove("hidden");
  const sDate = document.getElementById("admMbrStartDate");
  if (sDate && !sDate.value) {
    sDate.value = new Date().toISOString().split("T")[0];
  }
}

function closeAdminAddMemberModal() {
  document.getElementById("adminAddMemberModal")?.classList.add("hidden");
}

function onAdmMbrTypeChange() {
  const type = document.getElementById("admMbrType")?.value;
  const courtBox = document.getElementById("admMbrCourtBox");
  const timeBox = document.getElementById("admMbrTimeBox");
  const priceInput = document.getElementById("admMbrPrice");
  const durInput = document.getElementById("admMbrDuration");

  if (type === 'FIXED_COURT_MONTHLY') {
    if (courtBox) courtBox.classList.remove("hidden");
    if (timeBox) timeBox.classList.remove("hidden");
    if (durInput) durInput.value = 1;
  } else if (type === 'SOCIAL_YEAR') {
    if (courtBox) courtBox.classList.add("hidden");
    if (timeBox) timeBox.classList.add("hidden");
    if (durInput) durInput.value = 12;
    if (priceInput) priceInput.value = 5000000;
  } else if (type === 'SOCIAL_MONTH_MORNING') {
    if (courtBox) courtBox.classList.add("hidden");
    if (timeBox) timeBox.classList.add("hidden");
    if (durInput) durInput.value = 1;
    if (priceInput) priceInput.value = 600000;
  } else if (type === 'SOCIAL_MONTH_ALL') {
    if (courtBox) courtBox.classList.add("hidden");
    if (timeBox) timeBox.classList.add("hidden");
    if (durInput) durInput.value = 1;
    if (priceInput) priceInput.value = 1200000;
  }
}

async function submitAdminAddMember(e) {
  if (e) e.preventDefault();
  const name = document.getElementById("admMbrName")?.value.trim();
  const phone = document.getElementById("admMbrPhone")?.value.trim();
  const type = document.getElementById("admMbrType")?.value;
  const courtId = document.getElementById("admMbrCourtId")?.value;
  const timeSlots = document.getElementById("admMbrTimeSlots")?.value.trim();
  const price = parseInt(document.getElementById("admMbrPrice")?.value) || 0;
  const duration = parseInt(document.getElementById("admMbrDuration")?.value) || 1;
  const startDate = document.getElementById("admMbrStartDate")?.value;
  const payStatus = document.getElementById("admMbrPaymentStatus")?.value;
  const notes = document.getElementById("admMbrNotes")?.value.trim();

  if (!name || !phone) {
    alert("Vui lòng nhập Họ tên và Số điện thoại hội viên!");
    return;
  }

  try {
    const res = await fetch("/api/pickleball/memberships", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        customer_name: name,
        phone: phone,
        membership_type: type,
        court_id: type === 'FIXED_COURT_MONTHLY' ? (courtId || 'PK-01') : null,
        time_slots_desc: type === 'FIXED_COURT_MONTHLY' ? timeSlots : null,
        duration_months: duration,
        start_date: startDate || null,
        paid_amount: price,
        payment_status: payStatus,
        notes: notes
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    alert(`🎉 Đăng ký thành công hội viên [${name}]! Mã thẻ: ${data.member_code}`);
    closeAdminAddMemberModal();
    document.getElementById("adminAddMemberForm")?.reset();
    loadAdminMemberships();
  } catch (err) {
    alert("⚠️ " + err.message);
  }
}

function openAdminAddTransactionModal() {
  document.getElementById("adminAddTransactionModal")?.classList.remove("hidden");
  updateAdminTxExpenseOptions();
}

function closeAdminAddTransactionModal() {
  document.getElementById("adminAddTransactionModal")?.classList.add("hidden");
}

function updateAdminTxExpenseOptions() {
  const type = document.getElementById("admTxType")?.value;
  const costCatEl = document.getElementById("admTxCostCatWrapper");
  const costCat = document.getElementById("admTxCostCategory")?.value;
  const expTypeSelect = document.getElementById("admTxExpenseType");

  if (!expTypeSelect) return;

  if (type === 'INCOME') {
    if (costCatEl) costCatEl.classList.add("hidden");
    expTypeSelect.innerHTML = `
      <option value="Doanh thu F&B (Nhà hàng)">Doanh thu F&B (Nhà hàng)</option>
      <option value="Doanh thu Social Sân Pickle">Doanh thu Social Sân Pickle</option>
      <option value="Doanh thu Hội viên tháng/năm">Doanh thu Hội viên tháng/năm</option>
      <option value="Doanh thu Thuê sân Pickle">Doanh thu Thuê sân Pickle</option>
      <option value="Tài trợ & Quảng cáo sân">Tài trợ & Quảng cáo sân</option>
      <option value="Thu khác">Thu khác</option>
    `;
  } else {
    if (costCatEl) costCatEl.classList.remove("hidden");
    if (costCat === 'CAPEX') {
      expTypeSelect.innerHTML = `
        <option value="Đầu tư xây dựng sân Pickleball">Đầu tư xây dựng sân Pickleball</option>
        <option value="Hệ thống chiếu sáng sân Pickleball">Hệ thống chiếu sáng sân Pickleball</option>
        <option value="Mua sắm vợt & trang thiết bị Pickleball">Mua sắm vợt & trang thiết bị Pickleball</option>
        <option value="Trang thiết bị bếp & nhà hàng">Trang thiết bị bếp & nhà hàng</option>
        <option value="Nội thất bàn ghế & cảnh quan">Nội thất bàn ghế & cảnh quan</option>
        <option value="Hệ thống POS, máy in & CNTT">Hệ thống POS, máy in & CNTT</option>
        <option value="Khác (Capex)">Khác (Capex)</option>
      `;
    } else {
      expTypeSelect.innerHTML = `
        <option value="Nguyên vật liệu tươi sống & thực phẩm">Nguyên vật liệu tươi sống & thực phẩm</option>
        <option value="Bia, nước ngọt & đồ uống đóng chai">Bia, nước ngọt & đồ uống đóng chai</option>
        <option value="Tiền điện, nước, internet">Tiền điện, nước, internet</option>
        <option value="Lương & phụ cấp nhân viên">Lương & phụ cấp nhân viên</option>
        <option value="Bảo trì sân Pickleball (lưới, đèn, vệ sinh)">Bảo trì sân Pickleball (lưới, đèn, vệ sinh)</option>
        <option value="Bóng thi đấu & dụng cụ tiêu hao Pickleball">Bóng thi đấu & dụng cụ tiêu hao Pickleball</option>
        <option value="Thuê mặt bằng">Thuê mặt bằng</option>
        <option value="Marketing & Quảng cáo">Marketing & Quảng cáo</option>
        <option value="Văn phòng phẩm, hóa chất tẩy rửa & tạp phí">Văn phòng phẩm, hóa chất tẩy rửa & tạp phí</option>
        <option value="Khác (Opex)">Khác (Opex)</option>
      `;
    }
  }
}

async function submitAdminAddTransaction(e) {
  if (e) e.preventDefault();
  const txType = document.getElementById("admTxType")?.value;
  const costCat = txType === 'INCOME' ? 'OPEX' : document.getElementById("admTxCostCategory")?.value;
  const dept = document.getElementById("admTxDepartment")?.value;
  const expType = document.getElementById("admTxExpenseType")?.value;
  const amount = parseInt(document.getElementById("admTxAmount")?.value) || 0;
  const payMethod = document.getElementById("admTxPayMethod")?.value;
  const recipient = document.getElementById("admTxRecipient")?.value.trim();
  const desc = document.getElementById("admTxDesc")?.value.trim();
  const receiptUrl = document.getElementById("admReceiptUrl")?.value.trim() || "";

  if (amount <= 0) {
    alert("Vui lòng nhập số tiền hợp lệ (> 0 đ)!");
    return;
  }

  try {
    const res = await fetch("/api/accounting/transactions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        transaction_type: txType,
        cost_category: costCat,
        department: dept,
        expense_type: expType,
        amount: amount,
        payment_method: payMethod,
        recipient_payer: recipient,
        description: desc,
        receipt_url: receiptUrl
      })
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail);

    alert(`✅ Đã lập phiếu [${data.transaction_code || (data.transaction && data.transaction.transaction_code) || ''}] thành công!`);
    closeAdminAddTransactionModal();
    document.getElementById("adminAddTransactionForm")?.reset();
    clearAdminReceiptFile();
    loadAccountingPnL();
    loadAccountingLedger();
  } catch (err) {
    alert("⚠️ " + err.message);
  }
}

// Helpers Upload Anh Chung Tu (Admin)
async function handleAdminReceiptFileSelect(event) {
  const file = event.target.files && event.target.files[0];
  if (!file) return;

  const previewBox = document.getElementById("admReceiptPreviewBox");
  const previewImg = document.getElementById("admReceiptPreviewImg");
  const btnText = document.getElementById("admReceiptBtnText");

  if (previewImg) previewImg.src = URL.createObjectURL(file);
  if (previewBox) {
    previewBox.classList.remove("hidden");
    previewBox.classList.add("flex");
  }
  if (btnText) btnText.innerText = "Đang tải ảnh...";

  try {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch("/api/accounting/upload-receipt", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Không thể tải ảnh chứng từ lên.");

    const receiptUrlEl = document.getElementById("admReceiptUrl");
    if (receiptUrlEl) receiptUrlEl.value = data.receipt_url;
    if (btnText) btnText.innerText = "Đã chọn ảnh (Đổi)";
  } catch (err) {
    alert("❌ Lỗi tải ảnh: " + err.message);
    clearAdminReceiptFile();
  }
}

function clearAdminReceiptFile() {
  const fileInput = document.getElementById("admReceiptFileInput");
  const receiptUrlEl = document.getElementById("admReceiptUrl");
  const previewBox = document.getElementById("admReceiptPreviewBox");
  const previewImg = document.getElementById("admReceiptPreviewImg");
  const btnText = document.getElementById("admReceiptBtnText");

  if (fileInput) fileInput.value = "";
  if (receiptUrlEl) receiptUrlEl.value = "";
  if (previewImg) previewImg.src = "";
  if (previewBox) {
    previewBox.classList.add("hidden");
    previewBox.classList.remove("flex");
  }
  if (btnText) btnText.innerText = "Chọn ảnh hoặc Chụp ảnh";
}

function zoomReceiptImage(src) {
  if (!src) return;
  const modal = document.getElementById("receiptImageModal");
  const img = document.getElementById("receiptModalImg");
  const link = document.getElementById("receiptDownloadLink");
  if (img) img.src = src;
  if (link) link.href = src;
  if (modal) modal.classList.remove("hidden");
}

function closeReceiptImageModal() {
  const modal = document.getElementById("receiptImageModal");
  if (modal) modal.classList.add("hidden");
}
