/* Relatorio do scriptLattes dentro da pagina: o quadro cresce com o conteudo
   (mesma origem, entao da para medir), links externos abrem em outra aba e o
   relatorio herda a fonte do site. */
(function () {
	var q = document.getElementById('gemec-lattes-quadro');
	if (!q) return;
	var primeira = true;

	function doc() {
		try { return q.contentDocument; } catch (e) { return null; }
	}
	function medir() {
		var d = doc();
		if (!d || !d.documentElement) return;
		var h = Math.max(d.documentElement.scrollHeight, d.body ? d.body.scrollHeight : 0);
		if (h && Math.abs(q.offsetHeight - h) > 4) q.style.height = (h + 2) + 'px';
	}

	q.addEventListener('load', function () {
		var d = doc();
		if (!d) return;
		var css = d.createElement('style');
		css.textContent = 'body{font-family:"Inter",system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;background:#fff}';
		d.head && d.head.appendChild(css);
		d.addEventListener('click', function (ev) {
			var a = ev.target.closest && ev.target.closest('a[href]');
			if (a && a.host && a.host !== location.host) a.target = '_blank';
		});
		medir();
		// ao navegar dentro do relatorio, volta ao topo do quadro
		if (!primeira) q.scrollIntoView({ block: 'start' });
		primeira = false;
		if (window.ResizeObserver && d.body) new ResizeObserver(medir).observe(d.body);
	});
	setInterval(medir, 1500); // graficos e tabelas que montam depois do load
})();
