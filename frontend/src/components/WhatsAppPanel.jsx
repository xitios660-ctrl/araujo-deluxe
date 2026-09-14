import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { CheckCircle, Plugs, QrCode, SignOut } from "@phosphor-icons/react";
import { api, apiError } from "../lib/api";

export const WhatsAppPanel = () => {
  const [status, setStatus] = useState(null);
  const [qr, setQr] = useState(null);

  const poll = useCallback(async () => {
    try {
      const { data } = await api.get("/admin/whatsapp/status");
      setStatus(data);
      if (!data.connected && !data.offline) {
        const r = await api.get("/admin/whatsapp/qr");
        setQr(r.data.qr_base64 || null);
      } else {
        setQr(null);
      }
    } catch {
      setStatus({ connected: false, offline: true });
    }
  }, []);

  useEffect(() => {
    poll();
    const id = setInterval(poll, 4000);
    return () => clearInterval(id);
  }, [poll]);

  const logout = async () => {
    try {
      await api.post("/admin/whatsapp/logout");
      toast.success("Sessão encerrada. Um novo QR Code aparecerá em instantes.");
    } catch (e) {
      toast.error(apiError(e));
    }
  };

  return (
    <div className="bg-white rounded-3xl border border-border p-6 sm:p-8" data-testid="admin-whatsapp-panel">
      <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
        <div>
          <h2 className="font-display text-2xl text-foreground">Bot do WhatsApp</h2>
          <p className="text-muted-foreground text-sm mt-1">
            O bot agenda horários, mostra disponibilidade, recebe comprovantes e envia as confirmações automaticamente.
          </p>
        </div>
        {status?.connected ? (
          <span className="rounded-full bg-emerald-100 text-emerald-800 text-xs font-semibold px-4 py-2 flex items-center gap-2" data-testid="whatsapp-status-connected">
            <CheckCircle size={15} weight="fill" /> Conectado
          </span>
        ) : (
          <span className="rounded-full bg-amber-100 text-amber-800 text-xs font-semibold px-4 py-2 flex items-center gap-2" data-testid="whatsapp-status-disconnected">
            <Plugs size={15} /> {status?.offline ? "Serviço indisponível" : "Desconectado"}
          </span>
        )}
      </div>

      {status?.connected ? (
        <div className="max-w-lg" data-testid="whatsapp-connected-box">
          <p className="text-sm text-foreground">
            Número conectado: <span className="font-semibold">{(status.user?.id || "").split(":")[0].split("@")[0] || "—"}</span>
          </p>
          <ul className="text-muted-foreground text-sm mt-4 space-y-2 list-disc list-inside">
            <li>Clientes podem conversar com o bot para agendar e ver horários livres.</li>
            <li>Comprovantes enviados pelo site ou pelo WhatsApp confirmam a reserva na hora.</li>
            <li>Você recebe cada agendamento + comprovante no seu WhatsApp (5511997685110).</li>
          </ul>
          <button
            onClick={logout}
            className="mt-6 rounded-full border border-destructive/40 text-destructive text-xs font-semibold px-5 py-2.5 flex items-center gap-2 hover:bg-destructive/10 transition-colors duration-300"
            data-testid="whatsapp-logout-button"
          >
            <SignOut size={14} /> Desconectar / trocar número
          </button>
        </div>
      ) : (
        <div className="flex flex-col sm:flex-row gap-8 items-start">
          <div className="bg-muted rounded-3xl p-6 flex items-center justify-center min-w-[220px] min-h-[220px]" data-testid="whatsapp-qr-box">
            {qr ? (
              <img src={`data:image/png;base64,${qr}`} alt="QR Code WhatsApp" className="w-52 h-52 rounded-xl" data-testid="whatsapp-qr-image" />
            ) : (
              <div className="text-center text-muted-foreground text-xs">
                <QrCode size={40} className="mx-auto mb-3 text-primary" />
                {status?.offline ? "O bot não está respondendo. A conexão será verificada novamente automaticamente." : "Gerando QR Code…"}
              </div>
            )}
          </div>
          <div className="text-sm text-muted-foreground max-w-md">
            <p className="text-foreground font-semibold mb-3">Como conectar o número do bot:</p>
            <ol className="space-y-2 list-decimal list-inside">
              <li>No celular com o chip do bot, abra o <strong>WhatsApp</strong></li>
              <li>Toque em <strong>⋮ &gt; Aparelhos conectados</strong></li>
              <li>Toque em <strong>Conectar um aparelho</strong></li>
              <li>Aponte a câmera para o QR Code ao lado</li>
            </ol>
            <p className="mt-4 text-xs">O QR Code se renova sozinho. Depois de escanear, o bot fica online e responde os clientes automaticamente.</p>
          </div>
        </div>
      )}
    </div>
  );
};
