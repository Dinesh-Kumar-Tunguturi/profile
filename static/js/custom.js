// jquery ready start
$(document).ready(function () {

  $(window).scroll(function() {
			if ($(window).scrollTop() > 0) {
				$('.scroll-header').addClass('fixed-header');
			} else {
				$('.scroll-header').removeClass('fixed-header');
			}
		});

    // testimonails read more text    
    $(".read-more-link").click(function(){
        var moreText = $(this).prev(".short-text").find(".more-text");
        var linkText = $(this);
        if(moreText.is(":visible")) {
            moreText.slideUp();
            linkText.text("Read More");
        } else {
            moreText.slideDown();
            linkText.text("Read Less");
        }
        });	


        $("a.nav-link").on('click', function(event) {
            if (this.hash !== "") {
              event.preventDefault();
              var target = $(this.hash);
              var offset = 70; // Adjust for navbar height
              $('html, body').animate({
                scrollTop: target.offset().top - offset
              }, 0);
            }
          });
      
});  
 
 /*Menu Onclick*/
//     let sideMenuToggle = $(".menu-toggle");
//     let sideMenu = $(".side-menu");
//     if (sideMenuToggle.length) {
//         sideMenuToggle.on("click", function () {
//             $("body").addClass("overflow-hidden");
//             sideMenu.addClass("side-menu-active");
//             $(function () {
//                 setTimeout(function () {
//                     $(".side-menu-bg").fadeIn(300);
//                 }, 300);
//             });
//         });
//         $(".side-menu .btn-close, .side-menu-bg").on("click", function () {
//             $("body").removeClass("overflow-hidden");
//             sideMenu.removeClass("side-menu-active");
//             $(".side-menu-bg").fadeOut(200);
//         });
//         $(".side-nav-menu > .menu-item > .arrow").on("click", function () {
//           if ($(this).hasClass('open')) {
//             $(this).removeClass('open');
//             $(this).next('.sub-menu').slideUp();
//           } else {
//             $('.arrow').removeClass('open');
//             $('.side-menu .sub-menu').slideUp();
//             $(this).addClass('open');
//             $(this).next('.sub-menu').slideDown();
//           }
//         });
//         $(document).keyup(e => {
//             if (e.keyCode === 27) { // escape key maps to keycode `27`
//                 if (sideMenu.hasClass("side-menu-active")) {
//                     $("body").removeClass("overflow-hidden");
//                     sideMenu.removeClass("side-menu-active");
//                     $(".side-menu-bg").fadeOut(200);
//                 }
//             }
//         });
//     }


  // $(".nav-link111").on("click", function () {
  //     $("body").removeClass("overflow-hidden");
  //     $(".side-menu").removeClass("side-menu-active");
  //     $(".side-menu-bg").fadeOut(200);
  // });


const sideNav = document.getElementById('sideNav');
const overlay = document.getElementById('overlay');
const toggleBtn = document.getElementById('mobileMenuToggle');
const closeBtn = document.getElementById('closeSideNav');

toggleBtn.addEventListener('click', () => {
  sideNav.classList.add('active');
  overlay.classList.add('show');
});

closeBtn.addEventListener('click', () => {
  sideNav.classList.remove('active');
  overlay.classList.remove('show');
});

overlay.addEventListener('click', () => {
  sideNav.classList.remove('active');
  overlay.classList.remove('show');
});

// Toggle mobile submenu for "Services"
document.addEventListener('DOMContentLoaded', () => {
  const serviceToggle = document.querySelector('.mobile-dropdown-toggle');
  const submenu = serviceToggle?.nextElementSibling;

  if (serviceToggle && submenu) {
    serviceToggle.addEventListener('click', (e) => {
      e.preventDefault();
      submenu.classList.toggle('show');
    });
  }
});

document.querySelectorAll('.side-nav .close-drawer-on-click').forEach(link => {
  link.addEventListener('click', function () {
    const targetHref = this.getAttribute('href');

    const closeUrls = [
      'v2/#whyoutspak',
      'v2/#whothisfor',
      'v2/#careerpost',
      'contact'
    ];

    if (closeUrls.includes(targetHref)) {
      sideNav.classList.remove('active');
      overlay.classList.remove('show');
    }
  });
});
