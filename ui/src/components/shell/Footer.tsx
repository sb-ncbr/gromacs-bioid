import elixirLogo from "../../assets/elixirlogo.png";

export default function Footer() {
  return (
    <footer className="mt-12 bg-surface px-6 py-8 text-sm text-text-muted">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-6 md:flex-row md:items-start">
        <div className="shrink-0 px-4">
          <img src={elixirLogo} alt="ELIXIR Czech Republic Node" className="max-w-40" />
        </div>
        <div className="space-y-3">
          <p>
            <a href="/" className="font-bold text-text-heading no-underline">
              Molecular Dynamics <span className="text-primary">Bio</span>ID
            </a>{" "}
            tool is a part of services provided by ELIXIR – European research infrastructure for
            biological information. For other services provided by ELIXIR&rsquo;s Czech Republic
            Node visit{" "}
            <a
              href="https://www.elixir-czech.cz/services"
              className="text-primary underline"
            >
              elixir-czech.cz/services
            </a>
            .
          </p>
          <hr className="border-base-200" />
          <p>
            Licence conditions in accordance with &sect; 11 of Act No. 130/2002 Coll. The owner of
            the software is Masaryk University, a public university, ID: 00216224. Masaryk
            University allows other companies and individuals to use this software free of charge
            and without territorial restrictions in usual way, that does not depreciate its value.
            This permission is granted for the duration of property rights. This software is not
            subject to special information treatment according to Act No. 412/2005 Coll., as
            amended. In case that a person who will use the software under this licence offer
            violates the licence terms, the permission to use the software terminates.
          </p>
          <p>
            This work was supported by the ELIXIR CZ research infrastructure project (MEYS Grant
            No: LM2018131), and FR CESNET grant 759/2024.
          </p>
          <hr className="border-base-200" />
          <p>
            &copy; {new Date().getFullYear()} Made with ❤️ by{" "}
            <a href="https://sb.ncbr.muni.cz/en" className="text-primary underline">
              Structural Bioinformatics research group at Masaryk University
            </a>
          </p>
        </div>
      </div>
    </footer>
  );
}
