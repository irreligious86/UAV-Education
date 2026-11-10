/*
 * Interface translation for the browser (docs/I18N.md). The Russian source string is the key:
 *   T("Сдан")                    -> "Складено" on a Ukrainian page, "Сдан" if untranslated
 *   T("Шаг {i} из {n}", {i, n})  -> placeholders filled after translating
 * The catalog of the page's language is loaded before this file (assets/i18n/<lang>.js, generated).
 * Language choice: the header switcher stores "uav-lang" in localStorage; an early script in <head>
 * sends every later page to that language. A signed-in account's language (profiles.lang) overrides it.
 */
(function () {
  var cat = window.UAV_I18N_CATALOG || {};
  var root = document.documentElement;
  var lang = root.getAttribute("data-lang") || "ru";

  function T(s, vars) {
    var out = Object.prototype.hasOwnProperty.call(cat, s) ? cat[s] : s;
    if (vars) out = out.replace(/\{([a-z_][a-z0-9_]*)\}/g, function (m, k) { return k in vars ? String(vars[k]) : m; });
    return out;
  }

  function remember(code) { try { localStorage.setItem("uav-lang", code); } catch (e) { /* storage off */ } }
  function chosen() { try { return localStorage.getItem("uav-lang"); } catch (e) { return null; } }

  // URL of the current page in another language (from the hreflang alternates written by the build)
  function urlFor(code) {
    var l = document.querySelector('link[rel=alternate][hreflang="' + code + '"]');
    return l ? l.href : null;
  }

  // Switch: remember, tell the account (if signed in), go to the same page in that language.
  function switchTo(code) {
    remember(code);
    var go = function () { var u = urlFor(code); if (u && code !== lang) location.href = u + location.search.replace(/[?&]lang=keep\b/, "") + location.hash; };
    if (window.UAVAccount && window.UAVAccount.setLanguage) {
      window.UAVAccount.setLanguage(code).then(go, go);
    } else go();
  }

  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("[data-lang-to]");
    if (!a) return;
    e.preventDefault();
    switchTo(a.getAttribute("data-lang-to"));
  });

  // Only an explicit choice is remembered: a shared link to a page in another language opens as sent
  // until the visitor picks a language themselves.

  window.UAVI18N = { T: T, lang: lang, switchTo: switchTo, urlFor: urlFor, remember: remember, chosen: chosen };
  window.T = window.T || T;
})();
