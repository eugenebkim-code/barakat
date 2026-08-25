<script setup>
import { computed, onMounted, ref } from 'vue';

const products = ref([]);
const categories = ref([]);
const cart = ref({});
const selectedCategory = ref('');
const screen = ref('welcome');
const loading = ref(false);
const error = ref('');

const money = (value) => `${Number(value || 0).toLocaleString()}₩`;

const filteredProducts = computed(() => {
  if (!selectedCategory.value) return [];
  return products.value.filter(
    (p) => p.category === selectedCategory.value && p.available
  );
});

const getProduct = (productId) =>
  products.value.find((p) => p.product_id === productId);

const cartItems = computed(() =>
  Object.entries(cart.value)
    .map(([productId, qty]) => {
      const product = getProduct(productId);
      if (!product) return null;
      return { ...product, qty };
    })
    .filter(Boolean)
);

const subtotal = computed(() =>
  cartItems.value.reduce((sum, item) => sum + item.price * item.qty, 0)
);

const deliveryFee = computed(() => {
  if (subtotal.value >= 30000) return 0;
  return cartItems.value.length ? 4000 : 0;
});

const total = computed(() => subtotal.value + deliveryFee.value);

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

const openCategory = (category) => {
  selectedCategory.value = category;
  screen.value = 'products';
};

const goToCategories = () => {
  screen.value = 'categories';
};

const goToCart = () => {
  screen.value = 'cart';
};

const startOrder = () => {
  screen.value = 'categories';
};

const fetchProducts = async () => {
  loading.value = true;
  error.value = '';

  try {
    const response = await fetch('/api/products');
    if (!response.ok) throw new Error('Не удалось загрузить каталог');
    const data = await response.json();
    products.value = data.products || [];
    categories.value = data.categories || [];
    if (categories.value.length && !selectedCategory.value) {
      selectedCategory.value = categories.value[0];
    }
  } catch (e) {
    error.value = e.message || 'Не удалось загрузить товары';
  } finally {
    loading.value = false;
  }
};

const submitOrder = async () => {
  if (!Object.keys(cart.value).length) {
    error.value = 'Корзина пуста';
    return;
  }

  loading.value = true;
  error.value = '';

  try {
    const payload = {
      user_id: 0,
      username: 'miniapp-user',
      cart: cart.value,
      kind: 'pickup',
      address: '',
      comment: '',
      payment_proof: '',
    };

    const response = await fetch('/api/orders', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || 'Не удалось оформить заказ');

    alert(`Заказ создан. ID: ${data.order_id}`);
    clearCart();
    screen.value = 'welcome';
  } catch (e) {
    error.value = e.message || 'Ошибка оформления заказа';
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  fetchProducts();
});
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">BARAKAT</div>
      <div class="status">Доставка · Самовывоз</div>
    </header>

    <div v-if="loading" class="message-box info">Загрузка...</div>
    <div v-if="error" class="message-box error">{{ error }}</div>

    <div v-if="screen === 'welcome'" class="welcome-screen">
      <div class="welcome-card">
        <div class="welcome-badge">☪️ ХАЛАЛ</div>
        <h1>Добро пожаловать в BARAKAT</h1>
        <p>
          Традиционная узбекская кухня по домашним рецептам.<br />
          Свежие блюда, вкус и уют в каждом заказе.
        </p>

        <button class="primary-btn" @click="startOrder">Открыть каталог</button>
      </div>
    </div>

    <div v-else class="content-grid">
      <aside class="panel left-panel">
        <div class="panel-header">
          <h3>{{ screen === 'categories' ? 'Категории' : selectedCategory }}</h3>
          <button class="mini-btn" @click="goToCart">Корзина ({{ cartItems.length }})</button>
        </div>

        <div v-if="screen === 'categories'" class="category-list">
          <button
            v-for="category in categories"
            :key="category"
            class="category-card"
            @click="openCategory(category)"
          >
            <span>{{ category }}</span>
            <strong>→</strong>
          </button>
        </div>

        <div v-else-if="screen === 'products'" class="product-list">
          <button class="back-btn" @click="goToCategories">← Назад</button>

          <div v-for="product in filteredProducts" :key="product.product_id" class="product-card">
            <div class="product-top">
              <div>
                <h4>{{ product.name }}</h4>
                <div class="price">{{ money(product.price) }}</div>
              </div>
              <button class="mini-btn" @click="addToCart(product)">+ Добавить</button>
            </div>
            <p v-if="product.description" class="product-description">{{ product.description }}</p>
          </div>
        </div>
      </aside>

      <main class="panel right-panel">
        <div class="panel-header">
          <h3>Корзина</h3>
          <button class="mini-btn ghost" @click="clearCart">Очистить</button>
        </div>

        <button v-if="cartItems.length" class="back-btn" @click="goToCategories">← Вернуться в каталог</button>

        <div v-if="!cartItems.length" class="empty-state">
          Ваша корзина пока пустая.
        </div>

        <div v-else class="cart-list">
          <div v-for="item in cartItems" :key="item.product_id" class="cart-item">
            <div>
              <strong>{{ item.name }}</strong>
              <div>{{ item.qty }} × {{ money(item.price) }}</div>
            </div>

            <div class="cart-actions">
              <button @click="removeFromCart(item.product_id)">−</button>
              <button @click="addToCart(getProduct(item.product_id))">+</button>
            </div>
          </div>

          <div class="summary-box">
            <div class="summary-row">
              <span>Сумма</span>
              <strong>{{ money(subtotal) }}</strong>
            </div>
            <div class="summary-row">
              <span>Доставка</span>
              <strong>{{ deliveryFee ? money(deliveryFee) : 'Бесплатно' }}</strong>
            </div>
            <div class="summary-row total-row">
              <span>Итого</span>
              <strong>{{ money(total) }}</strong>
            </div>
          </div>

          <button class="primary-btn full-width" @click="submitOrder">Оформить заказ</button>
        </div>
      </main>
    </div>
  </div>
</template>
