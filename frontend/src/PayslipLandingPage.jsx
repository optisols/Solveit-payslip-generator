import React, { useState } from "react";
import { motion } from "framer-motion";

/**
 * Self-contained PayslipLandingPage (no shadcn/ui)
 * Requires: framer-motion, tailwindcss
 */

export default function PayslipLandingPage() {
  const [form, setForm] = useState({
    companyName: "SOLVEIT",
    companyAddress: "",
    payslipMonth: "",
    location: "",
    salaryRegisterFile: null,
  });
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState(0);

  function updateField(key, value) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function handleFileChange(e) {
    const file = e.target.files && e.target.files[0];
    if (file) updateField("salaryRegisterFile", file);
  }

  function handleSubmit(e) {
    e.preventDefault();
    if (!form.salaryRegisterFile) {
      setStatus("Please choose a salary register file first.");
      return;
    }

    setStatus("Uploading and generating payslips...");
    setProgress(1);

    const fd = new FormData();
    fd.append("company_name", form.companyName);
    fd.append("company_address", form.companyAddress);
    fd.append("payslip_month", form.payslipMonth);
    fd.append("location", form.location);
    fd.append("salary_file", form.salaryRegisterFile);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/generate_payslip");
    xhr.responseType = "blob";

    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) setProgress(Math.round((e.loaded / e.total) * 100));
    };

    xhr.onload = () => {
      if (xhr.status === 200) {
        const blob = xhr.response;
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Payslips_${form.payslipMonth || "month"}.zip`;
        a.click();
        setStatus("Payslips generated successfully and downloaded.");
      } else {
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const json = JSON.parse(reader.result);
            setStatus(json.message || `Server error ${xhr.status}`);
          } catch (err) {
            setStatus(`Server returned status ${xhr.status}`);
          }
        };
        reader.readAsText(xhr.response);
      }
      setProgress(0);
    };

    xhr.onerror = () => {
      setStatus("Error: Unable to reach server. Ensure backend is running.");
      setProgress(0);
    };

    xhr.send(fd);
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-white to-sky-50 p-6">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
        className="w-full max-w-4xl"
      >
        <div className="bg-white rounded-2xl shadow-2xl overflow-hidden border border-gray-100">
          <div className="md:flex">
            {/* Left panel */}
            <div className="md:w-1/3 bg-gradient-to-b from-sky-500 to-blue-700 p-8 text-white">
              <h2 className="text-2xl font-bold">SOLVEIT Payslip Generator</h2>
              <p className="text-sm mt-2 opacity-95">Create professional payslips from your salary register — fast & secure.</p>

              <ul className="mt-5 space-y-2 text-sm">
                <li className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" />
                  Auto ZIP & Archive
                </li>
                <li className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" />
                  Single-click generation
                </li>
                <li className="flex items-center gap-3">
                  <span className="w-2 h-2 rounded-full bg-yellow-400 inline-block" />
                  Responsive UI
                </li>
              </ul>
            </div>

            {/* Right form */}
            <div className="md:w-2/3 p-8">
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Company Name</label>
                    <input
                      type="text"
                      value={form.companyName}
                      onChange={(e) => updateField("companyName", e.target.value)}
                      className="mt-1 block w-full rounded-lg border border-gray-200 p-3 focus:outline-none focus:ring-2 focus:ring-yellow-300"
                      placeholder="SOLVEIT"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Payslip Month</label>
                    <input
                      type="month"
                      value={form.payslipMonth}
                      onChange={(e) => updateField("payslipMonth", e.target.value)}
                      className="mt-1 block w-full rounded-lg border border-gray-200 p-3 focus:outline-none focus:ring-2 focus:ring-yellow-300"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Company Address</label>
                  <textarea
                    value={form.companyAddress}
                    onChange={(e) => updateField("companyAddress", e.target.value)}
                    className="mt-1 block w-full rounded-lg border border-gray-200 p-3 focus:outline-none focus:ring-2 focus:ring-yellow-300"
                    rows={3}
                    placeholder="Company address"
                    required
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Location</label>
                    <input
                      type="text"
                      value={form.location}
                      onChange={(e) => updateField("location", e.target.value)}
                      className="mt-1 block w-full rounded-lg border border-gray-200 p-3 focus:outline-none focus:ring-2 focus:ring-yellow-300"
                      placeholder="Office location"
                      required
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Upload Salary Register</label>
                    <label className="mt-1 flex items-center justify-between gap-4 rounded-lg border border-dashed border-gray-200 p-3 cursor-pointer hover:bg-gray-50 transition-colors">
                      <span className="text-sm text-gray-600">
                        {form.salaryRegisterFile ? form.salaryRegisterFile.name : "Choose an Excel (.xls/.xlsx/.xlsm/.csv)"}
                      </span>
                      <input type="file" accept=".xls,.xlsx,.xlsm,.csv" onChange={handleFileChange} className="hidden" required />
                    </label>
                  </div>
                </div>

                <div className="flex flex-col sm:flex-row items-center gap-3">
                  <button
                    type="submit"
                    className="w-full sm:w-auto inline-flex items-center gap-2 bg-yellow-400 hover:bg-yellow-500 text-gray-900 font-semibold px-6 py-3 rounded-lg shadow-md transition-transform transform hover:-translate-y-0.5"
                  >
                    Generate Payslips
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setForm({ companyName: "SOLVEIT", companyAddress: "", payslipMonth: "", location: "", salaryRegisterFile: null });
                      setStatus("");
                      setProgress(0);
                    }}
                    className="w-full sm:w-auto inline-flex items-center gap-2 border border-gray-200 text-gray-700 px-5 py-3 rounded-lg hover:bg-gray-50"
                  >
                    Reset
                  </button>

                  <div className="ml-auto text-sm text-gray-500">{progress > 0 && progress < 100 ? `${progress}%` : ""}</div>
                </div>

                {progress > 0 && progress < 100 && (
                  <div className="w-full bg-gray-100 h-2 rounded overflow-hidden">
                    <div className="h-2 bg-yellow-400 transition-all duration-300" style={{ width: `${progress}%` }} />
                  </div>
                )}

                {status && (
                  <div className="rounded-lg p-3 text-sm" style={{ background: "linear-gradient(90deg,#e6f7ff, #fffbe6)" }}>
                    {status}
                  </div>
                )}

                <div className="text-xs text-gray-400">
                  Tip: Generated ZIPs are archived in <code>C:\\Projects\\payslip\\generated_zips</code>
                </div>
              </form>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
