<script setup>
import { computed, onMounted, ref } from 'vue';

const products = ref([]);
const categories = ref([]);
const cart = ref({});
const checkout = ref({
  step: 'catalog',
  name: '',
  phone: '',
  kind: 'pickup',
  address: '',
  comment: '',
  paymentProof: '',
});
const loading = ref(false);
const orderResult = ref(null);
const error = ref('');

const money = (value) => `${Number(value || 0).toLocaleString()}₩`;

const subtotal = computed(() => {
  return products.value.reduce((sum, p) => {
    const qty = cart.value[p.product_id] || 0;
    return sum + (qty * p.price);
  }, 0);
});

const deliveryFee = computed(() => {
  if (checkout.value.kind !== 'delivery') return 0;
  return subtotal.value >= 30000 ? 0 : 4000;
});

const total = computed(() => subtotal.value + deliveryFee.value);

const getProduct = (productId) => products.value.find((p) => p.product_id === productId);

const addToCart = (product) => {
  cart.value[product.product_id] = (cart.value[product.product_id] || 0) + 1;
};

const removeFromCart = (productId) => {
  if (!cart.value[productId]) return;
  cart.value[productId] -= 1;
  if (cart.value[productId] <= 0) delete cart.value[productId];
};

const clearCart = () => {
  cart.value = {};
};

const fetchProducts = async () => {
  loading.value = true;
  error.value = '';
  try {
    const response = await fetch('/api/products');
    if (!response.ok) throw new Error('Failed to load catalog');
    const data = await response.json();
    products.value = data.products || [];
    categories.value = data.categories || [];
  } catch (e) {
    error.value = e.message || 'Unable to load products';
  } finally {
    loading.value = false;
  }
};

const selectKind = (kind) => {
  checkout.value.kind = kind;
  checkout.value.step = 'form';
};

const submitOrder = async () => {
  if (!Object.keys(cart.value).length) {
    error.value = 'Your cart is empty';
    return;
  }

  if (!checkout.value.name || !checkout.value.phone) {
    error.value = 'Add your name and phone number';
    return;
  }

  loading.value = true;
  error.value = '';

  try {
    const payload = {
      user_id: 0,
      username: 'miniapp-user',
      cart: cart.value,
      kind: checkout.value.kind,
      address: checkout.value.address,
      comment: checkout.value.comment,
      payment_proof: checkout.value.paymentProof,
    };

    const response = await fetch('/api/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Could not create order');

    orderResult.value = data;
    checkout.value.step = 'success';
    clearCart();
  } catch (e) {
    error.value = e.message || 'Order failed';
  } finally {
    loading.value = false;
  }
};

const cartItems = computed(() => {
  return Object.entries(cart.value).map(([productId, qty]) => {
    const product = getProduct(productId);
    if (!product) return null;
    return { ...product, qty };
  }).filter(Boolean);
});

const formatStepLabel = () => {
  if (checkout.value.step === 'catalog') return 'Catalog';
  if (checkout.value.step === 'kind') return 'Delivery method';
  if (checkout.value.step === 'form') return 'Customer info';
  if (checkout.value.step === 'success') return 'Success';
  return 'Order';
};

onMounted(() => {
  fetchProducts();
});
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">BARAKAT</div>
      <div class="status">Mini app</div>
    </header>

    <div class="layout">
      <aside class="catalog-panel">
        <div class="panel-header">
          <h3>Catalog</h3>
          <span>{{ products.length }} items</span>
        </div>

        <div v-if="loading" class="muted">Loading...</div>
        <div v-if="error" class="error-box">{{ error }}</div>

        <div v-for="cat in categories" :key="cat" class="category-block">
          <h4>{{ cat }}</h4>
          <div v-for="product in products.filter((p) => p.category === cat)" :key="product.product_id" class="product-card">
            <div class="product-meta">
              <div>
                <strong>{{ product.name }}</strong>
                <div class="price">{{ money(product.price) }}</div>
              </div>
              <button @click="addToCart(product)">Add</button>
            </div>
            <div v-if="product.description" class="description">{{ product.description }}</div>
          </div>
        </div>
      </aside>

      <main class="checkout-panel">
        <div class="panel-header">
          <h3>{{ formatStepLabel() }}</h3>
          <button class="ghost" @click="clearCart">Clear cart</button>
        </div>

        <div v-if="!cartItems.length" class="empty-state">
          Cart is empty.
        </div>

        <div v-else class="cart-list">
          <div v-for="item in cartItems" :key="item.product_id" class="cart-item">
            <div>
              <strong>{{ item.name }}</strong>
              <div>{{ item.qty }} × {{ money(item.price) }}</div>
            </div>
            <div class="cart-actions">
              <button @click="removeFromCart(item.product_id)">−</button>
              <button @click="addToCart(item)">+</button>
            </div>
          </div>

          <div class="totals">
            <div><span>Subtotal</span><strong>{{ money(subtotal) }}</strong></div>
            <div><span>Delivery</span><strong>{{ checkout.kind === 'delivery' ? money(deliveryFee) : '0₩' }}</strong></div>
            <div class="grand-total"><span>Total</span><strong>{{ money(total) }}</strong></div>
          </div>
        </div>

        <div class="choice-block" v-if="checkout.step === 'catalog' || checkout.step === 'kind'">
          <button class="primary" @click="checkout.step = 'kind'">Choose order type</button>
        </div>

        <div v-if="checkout.step === 'kind'" class="choice-block">
          <button class="secondary" @click="selectKind('pickup')">Pickup</button>
          <button class="secondary" @click="selectKind('delivery')">Delivery</button>
        </div>

        <div v-if="checkout.step === 'form'" class="form-grid">
          <input v-model="checkout.name" placeholder="Full name" />
          <input v-model="checkout.phone" placeholder="Phone number" />
          <textarea v-model="checkout.comment" placeholder="Comment"></textarea>
          <input
            v-if="checkout.kind === 'delivery'"
            v-model="checkout.address"
            placeholder="Delivery address"
          />
          <input v-model="checkout.paymentProof" placeholder="Payment proof ID or reference" />
          <button class="primary" @click="submitOrder">Submit order</button>
        </div>

        <div v-if="checkout.step === 'success' && orderResult" class="success-box">
          <h3>Order sent</h3>
          <p>Order ID: {{ orderResult.order_id }}</p>
          <p>Total: {{ money(orderResult.total) }}</p>
        </div>
      </main>
    </div>
  </div>
</template>
