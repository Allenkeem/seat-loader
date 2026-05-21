// static/script.js

let seatsData = [];
let selectedSeats = [];
const MAX_SEATS = 4;
let currentSessionId = null;
let currentSessionName = "";

// =====================================================
// TOAST NOTIFICATION SYSTEM
// =====================================================
function showToast(message, type = 'info', duration = 3000) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(16px) scale(0.96)';
        toast.style.transition = 'opacity 0.25s ease, transform 0.25s ease';
        setTimeout(() => toast.remove(), 260);
    }, duration);
}

// =====================================================
// SEAT MAP
// =====================================================
async function fetchSeats() {
    if (!currentSessionId) return;

    const container = document.getElementById('seat-map');
    if (!seatsData.length) {
        container.innerHTML = '<div class="seat-map-loading">좌석 정보를 불러오는 중입니다…</div>';
    }

    try {
        const response = await fetch('/api/seats?session_id=' + currentSessionId);
        seatsData = await response.json();
        renderSeatMap();
    } catch (error) {
        container.innerHTML = '<div class="seat-map-loading">불러오기 실패. 새로고침 해주세요.</div>';
        console.error("Failed to fetch seats", error);
    }
}

function renderSeatMap() {
    const container = document.getElementById('seat-map');
    container.innerHTML = '';

    const rows = ["A", "B", "C", "D", "E", "F", "G"];

    rows.forEach(rowLetter => {
        if (rowLetter === 'E') {
            const fence = document.createElement('div');
            fence.className = 'seat-fence';
            fence.textContent = '— 펜스 —';
            container.appendChild(fence);
        }

        const label = document.createElement('div');
        label.className = 'row-label';
        label.innerText = rowLetter;
        container.appendChild(label);

        for (let num = 1; num <= 12; num++) {
            const seatWrapper = document.createElement('div');
            const seatInfo = seatsData.find(s => s.row === rowLetter && s.number === num);

            if (seatInfo) {
                seatWrapper.className = `seat ${seatInfo.status}`;
                if (selectedSeats.find(s => s.id === seatInfo.id) && seatInfo.status === 'available') {
                    seatWrapper.classList.add('selected');
                }

                seatWrapper.innerText = num;

                if (seatInfo.status === 'available') {
                    seatWrapper.onclick = () => toggleSeatSelection(seatInfo);
                }
            } else {
                seatWrapper.className = 'seat empty';
            }
            container.appendChild(seatWrapper);
        }
    });

    adjustStageWidth();
    updateSidebar();
}

function adjustStageWidth() {
    const seatMap = document.getElementById('seat-map');
    const stage = document.querySelector('.stage');
    const leftPanel = document.querySelector('.left-panel');
    if (!seatMap || !stage || !leftPanel || seatMap.children.length < 13) return;

    const first = seatMap.children[1].getBoundingClientRect();
    const last  = seatMap.children[12].getBoundingClientRect();
    const panelStyle = getComputedStyle(leftPanel);
    const panelContentLeft = leftPanel.getBoundingClientRect().left
        + parseFloat(panelStyle.borderLeftWidth || 0)
        + parseFloat(panelStyle.paddingLeft);

    stage.style.alignSelf   = 'flex-start';
    stage.style.width       = (last.right - first.left) + 'px';
    stage.style.maxWidth    = 'none';
    stage.style.marginLeft  = (first.left - panelContentLeft) + 'px';
    stage.style.marginRight = '0';
}

function toggleSeatSelection(seatInfo) {
    if (seatInfo.status !== 'available') return;

    const index = selectedSeats.findIndex(s => s.id === seatInfo.id);
    if (index > -1) {
        selectedSeats.splice(index, 1);
    } else {
        if (selectedSeats.length >= MAX_SEATS) {
            showToast(`최대 ${MAX_SEATS}석까지만 선택할 수 있습니다.`, 'info');
            return;
        }
        selectedSeats.push(seatInfo);
    }

    renderSeatMap();
}

function updateSidebar() {
    const listContainer = document.getElementById('selected-seats-list');
    const submitBtn = document.getElementById('submit-btn');
    const agreed = document.getElementById('privacy-agree')?.checked ?? false;

    if (selectedSeats.length === 0) {
        listContainer.innerHTML = '선택된 좌석이 없습니다.';
        submitBtn.disabled = true;
    } else {
        listContainer.innerHTML = selectedSeats.map(s =>
            `<span class="selected-seat-badge">${s.row}-${s.number}</span>`
        ).join('');
        submitBtn.disabled = !agreed;
    }

    updateMobileBookingBar();
}

document.getElementById('privacy-agree').addEventListener('change', updateSidebar);

// =====================================================
// MOBILE FLOATING BOOKING BAR
// =====================================================
function updateMobileBookingBar() {
    const bar = document.getElementById('mobile-booking-bar');
    if (!bar) return;

    const label = document.getElementById('mobile-bar-label');
    const badges = document.getElementById('mobile-bar-badges');

    if (selectedSeats.length > 0) {
        bar.classList.add('visible');
        label.textContent = `${selectedSeats.length}석 선택됨`;
        badges.innerHTML = selectedSeats.map(s =>
            `<span class="selected-seat-badge">${s.row}-${s.number}</span>`
        ).join('');
    } else {
        bar.classList.remove('visible');
    }
}

function scrollToBookingForm() {
    document.querySelector('.right-panel').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

// =====================================================
// RESERVATION FORM SUBMIT
// =====================================================
document.getElementById('reservation-form').onsubmit = async (e) => {
    e.preventDefault();
    if (selectedSeats.length === 0) return;

    const userName = document.getElementById('user-name').value;
    const phone = document.getElementById('phone').value;
    const password = document.getElementById('password').value;
    const privacyAgree = document.getElementById('privacy-agree');

    if (!privacyAgree.checked) {
        showToast('개인정보 수집 및 이용에 동의해주세요.', 'error');
        return;
    }

    if (phone.length < 10) {
        showToast('전화번호를 10자리 이상 숫자로 입력해주세요.', 'error');
        return;
    }

const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.innerText = '처리중...';

    try {
        const res = await fetch('/api/reserve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: currentSessionId,
                seat_ids: selectedSeats.map(s => s.id),
                user_name: userName,
                phone: phone,
                password: password
            })
        });

        if (res.ok) {
            showToast('예매가 완료되었습니다!', 'success', 4000);
            selectedSeats = [];
            document.getElementById('reservation-form').reset();
            document.getElementById('password').value = '';
            document.getElementById('privacy-agree').checked = false;
            updateMobileBookingBar();
            fetchSeats();
        } else {
            let detail = '다시 시도해주세요.';
            try {
                const error = await res.json();
                detail = error.detail || detail;
            } catch (_) {}
            showToast(`예매 실패: ${detail}`, 'error');
            fetchSeats();
        }
    } catch (err) {
        showToast('네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요.', 'error');
    } finally {
        btn.disabled = selectedSeats.length === 0;
        btn.innerText = '예매 확정';
    }
};

window.addEventListener('resize', adjustStageWidth);

// =====================================================
// SCROLL HINT (view-info)
// =====================================================
window.addEventListener('scroll', () => {
    const hint = document.getElementById('scroll-hint');
    if (!hint) return;
    if (window.scrollY > 60) {
        hint.classList.add('hidden');
    } else {
        hint.classList.remove('hidden');
    }
});

// =====================================================
// SESSION LOGIC
// =====================================================
loadSessions();
setInterval(() => {
    if (document.getElementById('view-booking').classList.contains('active') && currentSessionId) {
        fetchSeats();
    }
}, 5000);

async function loadSessions() {
    try {
        const response = await fetch('/api/sessions');
        const sessions = await response.json();
        const container = document.getElementById('session-buttons-container');
        container.innerHTML = sessions.map(s => {
            const full = s.available === 0;
            return `<button class="btn session-btn${full ? ' session-btn-full' : ''}" onclick="selectSession(${s.id}, '${s.name}')" ${full ? 'disabled' : ''}>
                <span class="session-btn-name">${s.name}</span>
                <span class="session-btn-sub">${s.subtitle || ''}</span>
                <span class="session-btn-avail${full ? ' avail-full' : ''}">${full ? '매진' : `잔여 ${s.available}석`}</span>
            </button>`;
        }).join('');
    } catch (e) { console.error('Failed to load sessions', e); }
}

function selectSession(id, name) {
    currentSessionId = id;
    currentSessionName = name;
    document.getElementById('booking-session-title').innerText = name + ' 예매';
    switchView('view-booking');
}

// =====================================================
// SPA VIEW SWITCHING — curtain transition
// =====================================================
function switchView(viewId) {
    const overlay = document.getElementById('page-overlay');

    // Fade to black (curtain down)
    overlay.classList.add('fading');

    setTimeout(() => {
        // Swap views while hidden
        document.querySelectorAll('.view-section').forEach(s => s.classList.remove('active'));
        document.getElementById(viewId).classList.add('active');
        window.scrollTo({ top: 0 });

        // Scroll hint visibility
        const hint = document.getElementById('scroll-hint');
        if (hint) hint.classList.toggle('hidden', viewId !== 'view-info');

        // View-specific setup
        if (viewId === 'view-booking') {
            fetchSeats();
        } else if (viewId === 'view-lookup') {
            document.getElementById('lookup-form').reset();
            document.getElementById('lookup-results').style.display = 'none';
            document.getElementById('my-reservations-list').innerHTML = '';
        }

        if (viewId !== 'view-booking') {
            selectedSeats = [];
            document.getElementById('reservation-form').reset();
            updateSidebar();
            const bar = document.getElementById('mobile-booking-bar');
            if (bar) bar.classList.remove('visible');
        }

        // Curtain up
        setTimeout(() => overlay.classList.remove('fading'), 30);
    }, 300);
}

// =====================================================
// LOOKUP FORM
// =====================================================
document.getElementById('lookup-form').onsubmit = async (e) => {
    e.preventDefault();

    const userName = document.getElementById('lookup-name').value;
    const phone = document.getElementById('lookup-phone').value;
    const password = document.getElementById('lookup-password').value;

    if (phone.length < 10) {
        showToast('전화번호를 10자리 이상 숫자로 입력해주세요.', 'error');
        return;
    }

    const btn = document.getElementById('lookup-btn');
    btn.disabled = true;
    btn.innerText = '로딩중...';

    try {
        const payload = { user_name: userName, phone: phone, password: password };
        const res = await fetch('/api/my_reservations', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (res.ok) {
            const data = await res.json();
            const list = document.getElementById('my-reservations-list');
            list.innerHTML = '';

            if (data.length === 0) {
                list.innerHTML = '<li style="color: var(--text-muted); font-size: 0.9rem;">예매 내역이 없습니다. (정보를 다시 확인해주세요)</li>';
            } else {
                data.forEach(r => {
                    const li = document.createElement('li');
                    li.className = 'reservation-item';
                    const displaySeat = r.seat_id.includes('_') ? r.seat_id.split('_')[1] : r.seat_id;
                    li.innerHTML = `
                        <div>
                            <span style="font-size: 0.8rem; color: #94a3b8; margin-right: 4px;">${r.session_id}회차</span>
                            <span class="reservation-seat">${displaySeat}</span> 좌석
                            <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 4px;">상태: ${r.claimed ? '<span style="color:#10b981">발권됨</span>' : '발권 대기중'}</div>
                        </div>
                        <button class="btn btn-secondary" style="padding: 0.4rem 0.8rem; font-size: 0.8rem; background: #ef4444; color: white; border: none; flex-shrink: 0;" onclick="cancelSeat('${r.seat_id}')">취소</button>
                    `;
                    list.appendChild(li);
                });
            }
            document.getElementById('lookup-results').style.display = 'block';
        } else {
            showToast('조회 실패: 입력 정보를 다시 확인해주세요.', 'error');
        }
    } catch (err) {
        showToast('네트워크 오류가 발생했습니다.', 'error');
    } finally {
        btn.disabled = false;
        btn.innerText = '조회하기';
    }
};

async function cancelSeat(seatId) {
    if (!confirm(`정말 ${seatId} 좌석 예매를 취소하시겠습니까?`)) return;

    const userName = document.getElementById('lookup-name').value;
    const phone = document.getElementById('lookup-phone').value;
    const password = document.getElementById('lookup-password').value;

    try {
        const res = await fetch(`/api/cancel/${seatId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_name: userName, phone: phone, password: password })
        });

        if (res.ok) {
            showToast(`${seatId} 좌석 예매가 취소되었습니다.`, 'success');
            document.getElementById('lookup-btn').click();
        } else {
            const err = await res.json();
            showToast('취소 실패: ' + err.detail, 'error');
        }
    } catch (err) {
        showToast('오류가 발생했습니다.', 'error');
    }
}
