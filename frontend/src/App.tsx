import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { siteUrl } from "./lib/api";
import { DocsPage } from "./pages/Docs";
import { LibraryPage } from "./pages/Library";
import { TemplatesPage } from "./pages/Templates";
import { WorkshopCtaPage } from "./pages/WorkshopCta";

/** The Kanz Market Close site's own header, so this reads as its "فريق كنز" tab: the logo, the site's
 * three tabs (the other two are on the page one folder up), then this site's pages as the inner tabs. */
function Header() {
  const home = siteUrl("../");
  return (
    <header className="site-head" dir="rtl" lang="ar">
      <div className="site-top">
        <div className="site-kick">Kanz · Market close reels</div>
        <a href={home} aria-label="Kanz Market Close">
          <img src={siteUrl("../kanz-white.png")} alt="Kanz" />
        </a>
      </div>
      <nav className="site-tabs" aria-label="أقسام الموقع">
        <a href={`${home}#videos`}>الفيديوهات</a>
        <a href={`${home}#posts`}>منشورات الإغلاق</a>
        <a href={siteUrl("")} aria-current="page">فريق كنز</a>
      </nav>
      <nav className="site-sub" aria-label="فريق كنز">
        <NavLink to="/library">المكتبة</NavLink>
        <NavLink to="/docs">دليل الهوية</NavLink>
        <NavLink to="/templates">القوالب</NavLink>
        <NavLink to="/workshop-cta">إعلان الورشة</NavLink>
        <a href={siteUrl("website/")}>موقع كنز</a>
      </nav>
    </header>
  );
}

export function App() {
  return (
    <div className="shell">
      <Header />
      <main>
        <Routes>
          <Route path="/library" element={<LibraryPage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="/docs/:slug" element={<DocsPage />} />
          <Route path="/templates" element={<TemplatesPage />} />
          <Route path="/templates/:slug" element={<TemplatesPage />} />
          <Route path="/workshop-cta" element={<WorkshopCtaPage />} />
          <Route path="*" element={<Navigate to="/library" replace />} />
        </Routes>
      </main>
    </div>
  );
}
