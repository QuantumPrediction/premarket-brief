(function(){
  function place(tip, box, x, y){
    var w = tip.offsetWidth, W = box.clientWidth;
    tip.style.left = Math.max(0, Math.min(W - w, x - w / 2)) + 'px';
    tip.style.top = Math.max(0, y - tip.offsetHeight - 14) + 'px';
  }
  function show(tip, head, rest){
    tip.textContent = '';
    var b = document.createElement('b'); b.textContent = head; tip.appendChild(b);
    var s = document.createElement('span'); s.textContent = rest; tip.appendChild(s);
    tip.hidden = false;
  }
  document.querySelectorAll('figure.chart[data-kind=line]').forEach(function(fig){
    var svg = fig.querySelector('svg'), tip = fig.querySelector('.tip');
    var pts = JSON.parse(fig.querySelector('.pts').textContent), g = JSON.parse(fig.querySelector('.geo').textContent);
    var cross = svg.querySelector('.cross'), hov = svg.querySelector('.hov'), idx = pts.length - 1;
    function at(i){
      idx = Math.max(0, Math.min(pts.length - 1, i));
      var p = pts[idx], x = g.l + g.pw * idx / (pts.length - 1), y = g.t + g.ph * (1 - p[1] / 100);
      cross.setAttribute('x1', x); cross.setAttribute('x2', x); cross.setAttribute('visibility', 'visible');
      hov.setAttribute('cx', x); hov.setAttribute('cy', y); hov.setAttribute('visibility', 'visible');
      var k = svg.clientWidth / g.W;
      show(tip, p[1].toFixed(1), p[0] + '  ' + (p[2] ? 'Regime ' + p[2] : ''));
      place(tip, fig, x * k, y * k);
    }
    function hide(){ cross.setAttribute('visibility', 'hidden'); hov.setAttribute('visibility', 'hidden'); tip.hidden = true; }
    svg.addEventListener('pointermove', function(ev){
      var r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width * g.W;
      at(Math.round((x - g.l) / g.pw * (pts.length - 1)));
    });
    svg.addEventListener('pointerleave', hide);
    svg.addEventListener('focus', function(){ at(idx); });
    svg.addEventListener('blur', hide);
    svg.addEventListener('keydown', function(ev){
      if (ev.key === 'ArrowLeft') { at(idx - 1); ev.preventDefault(); }
      if (ev.key === 'ArrowRight') { at(idx + 1); ev.preventDefault(); }
    });
  });
  document.querySelectorAll('.hbars').forEach(function(box){
    var tip = box.querySelector('.tip');
    box.querySelectorAll('.hrow').forEach(function(row){
      function on(){
        var parts = row.getAttribute('data-tip').split(' · ');
        show(tip, parts[0], parts.slice(1).join(' · '));
        var bar = row.querySelector('.htrack').getBoundingClientRect(), b0 = box.getBoundingClientRect();
        place(tip, box, bar.left - b0.left + bar.width / 2, row.getBoundingClientRect().top - b0.top);
      }
      row.addEventListener('pointerenter', on); row.addEventListener('focus', on);
      row.addEventListener('pointerleave', function(){ tip.hidden = true; });
      row.addEventListener('blur', function(){ tip.hidden = true; });
    });
  });
})();
