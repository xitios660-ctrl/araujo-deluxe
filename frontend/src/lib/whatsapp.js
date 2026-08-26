import { brand, formatBRL } from "../mock";

export function buildOrderMessage(order) {
  const lines = [
    `🐍 *NOVO PEDIDO — ${brand.name}*`,
    `Pedido: *${order.order_number}*`,
    ``,
    `*Itens:*`,
    ...order.items.map((i) => `• ${i.qty}x ${i.name} — ${formatBRL(i.price * i.qty)}`),
    ``,
    `Subtotal: ${formatBRL(order.subtotal)}`,
    `Frete (${order.shipping.label}): ${
      order.shipping.price === 0 ? "GRÁTIS" : formatBRL(order.shipping.price)
    }`,
    `*Total: ${formatBRL(order.total)}*`,
    ``,
    `*Cliente:* ${order.customer.name}`,
    `*Telefone:* ${order.customer.phone}`,
    order.customer.email ? `*E-mail:* ${order.customer.email}` : null,
    `*Endereço:* ${order.address.street}, ${order.address.number}${
      order.address.complement ? ` - ${order.address.complement}` : ""
    } — ${order.address.neighborhood ? `${order.address.neighborhood}, ` : ""}${
      order.address.city
    }/${order.address.state} — CEP ${order.address.cep}`,
    ``,
    `*Pagamento:* ${order.payment_method}`,
  ].filter((l) => l !== null);
  return lines.join("\n");
}

export const orderWhatsAppUrl = (order) =>
  `https://wa.me/${brand.whatsapp}?text=${encodeURIComponent(buildOrderMessage(order))}`;
